
# none -> nothing
# mq   -> prio combis (3 * 2 * 1 = 6 points)
# bfq  -> io weights (lets pick a few combis for a total of ~10.
#    [1000, 1 shared], [100, 1 shared], [10, 1 shared], [1, 1 shared], [1000, 1 * all other], [100, 1 * all other], [10, 1 * all other], [1 * all other], [1, 2], [1, 2]
#)
# io.lat -> pick some latency targets
# io.max -> set some max for the other group (shared), 
# io.cost -> set QoS to different values and set a few weights

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'util')))

from dataclasses import dataclass
from typing import Callable
import argparse
import itertools

import fio
from util_sysfs import cgroups as cgroups
from util_sysfs import nvme as nvme
from util_sysfs.bench import *
from util_sysfs.perf import *

EXPERIMENT_CGROUP_LC_PREAMBLE=f"lc-workload"
EXPERIMENT_CGROUP_BE_PREAMBLE=f"be-workload"
EXPERIMENT_CGROUP_PATH_PREAMBLE=f"example-workload"
EXPERIMENT_MAX_TENANT_COUNT=256

CORES = '1-10'
NUMJOBS = 8 + 1 # +1 to force 1 LC-tenants
CONFIG_POINT_FORCED = False
CONFIG_POINT = 0

@dataclass
class IOKnob:
    name: str
    points: int
    configure_cgroups: Callable[[nvme.NVMeDevice, list[cgroups.Cgroup]], None]

@dataclass
class Experiment:
    name: str
    change_jobs: bool

def none_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], point: int):
    return "none"

def mq_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], point: int):
    nvme_device.io_scheduler = nvme.IOScheduler.MQ_DEADLINE

    l = [cgroups.IOPriorityClass.IDLE, cgroups.IOPriorityClass.RESTRICT_TO_BE, cgroups.IOPriorityClass.PROMOTE_TO_RT]
    o = list(itertools.product(l, l))
    p = o[point % 9]

    exp_cgroups[0].ioprio = p[0]
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].ioprio = p[1]

    print(f"LC={p[0]} other={p[1]}%")

def mq2_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], point: int):
    nvme_device.io_scheduler = nvme.IOScheduler.MQ_DEADLINE
    nvme_device.set_ioscheduler_parameter("read_expire", "0")
    nvme_device.set_ioscheduler_parameter("fifo_batch", "1")
    nvme_device.set_ioscheduler_parameter("front_merges", "0")

    l = [cgroups.IOPriorityClass.IDLE, cgroups.IOPriorityClass.RESTRICT_TO_BE, cgroups.IOPriorityClass.PROMOTE_TO_RT]
    o = list(itertools.product(l, l))
    p = o[point % 9]

    exp_cgroups[0].ioprio = p[0]
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].ioprio = p[1]

    print(f"LC={p[0]} other={p[1]}%")

def iomax_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], point):
    max_ios = list(range(80, 2380, 80))
    max_io = max_ios[point % len(max_ios)]

    print(f"set BE-app io.max = {max_io} MiB/s")

    major_minor = nvme_device.major_minor
    for index, group in enumerate(exp_cgroups):
        if index == 0:
            continue
        group.iomax = cgroups.IOMax(major_minor, int(1024 * 1024 * max_io), int(1024 * 1024 * max_io), 10_000_000, 10_000_000)

def bfq2_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], point: int):
    nvme_device.io_scheduler = nvme.IOScheduler.BFQ
    nvme_device.set_ioscheduler_parameter("low_latency", "0")
    nvme_device.set_ioscheduler_parameter("slice_idle", "1")

    weights = [1/64, 1/32, 1/16, 1/8, 1] + list(range(25, 1025, 25))
    weight = weights[point % len(weights)]
    lc_weight = int(weight if weight >= 1 else 1)
    be_weight = int(1 if weight >= 1 else (1 // weight))
    print(f"Using io.bfq.weight={lc_weight}/{be_weight}")

    exp_cgroups[0].iobfqweight = cgroups.IOBFQWeight("default", lc_weight)
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].iobfqweight = cgroups.IOBFQWeight("default", be_weight)


def iolat_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], point: int):
    major_minor = nvme_device.major_minor

    #lats = [10, 70, 100, 200, 500]
    lats = list(range(25, 1150, 25))
    lat = lats[point % len(lats)]
    print(f"Using latency target={lat}")
    exp_cgroups[0].iolatency = cgroups.IOLatency(major_minor, lat)

def iocost_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], point: int):
    #min_scalings = [10.0, 50.0]
    #min_scaling = min_scalings[point // 27]
    #model_amplifiers = [1/2, 1/8, 1]
    #model_amplifier = model_amplifiers[(point % 27) // 9]
    #read_targets = [1_000, 100, 25]
    #read_target =  read_targets[2 - ((point % 9) // 3)]  
    #weights = [1, 10, 10000]
    #weight = weights[point % 3]

    # ?
    min_scalings = [1, 25, 50, 75, 100]
    min_scaling = min_scalings[point // 9]
    model_amplifier = 1
    read_targets = [25, 100, 1_000]
    read_target = read_targets[(point // 3) % 3]
    weights = [1/8, 1, 10_000]
    weight = weights[point % 3]
    lc_weight = int(weight if weight >= 1 else 1)
    be_weight = int(1 if weight >= 1 else (1 // weight))

    # We focus on bandwidth here, so sacrifice latency, we do not need it as a sign of congestion as it complicates matters 
    qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 99.00, read_target, 95.00, 1_000_000, min_scaling, 150.00)
    model = cgroups.get_iocostmodel_from_nvme_model(nvme_device, False, model_amplifier)
    cgroups.set_iocost(model, qos)


    print(f"Using weight={lc_weight}/{be_weight} model_amplifier={model_amplifier} read_target_us={read_target} min_scaling={min_scaling}%")
    exp_cgroups[0].ioweight = cgroups.IOWeight("default", lc_weight)
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].ioweight = cgroups.IOWeight("default", be_weight)

def iocost2_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], point: int):
    min_scalings = [95, 75, 50, 25, 10]
    min_scaling = min_scalings[point // 7]
    read_target = 1_000_000
    weights = [1/1000, 1/4, 1, 10, 100, 1000, 10_000]
    weight = weights[point % 7]
    lc_weight = int(weight if weight >= 1 else 1)
    be_weight = int(1 if weight >= 1 else (1 // weight))

    # We focus on bandwidth here, so sacrifice latency, we do not need it as a sign of congestion as it complicates matters 
    qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 99.00, read_target, 95.00, 1_000_000, min_scaling, 150.00)
    model = cgroups.get_iocostmodel_from_nvme_model(nvme_device, False, 1)
    cgroups.set_iocost(model, qos)

    print(f"Using weight={lc_weight}/{be_weight} model_amplifier=1 read_target_us={read_target} min_scaling={min_scaling}%")
    exp_cgroups[0].ioweight = cgroups.IOWeight("default", lc_weight)
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].ioweight = cgroups.IOWeight("default", be_weight)

def iocost3_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], point: int):
    min_scalings = [95, 75, 50, 25, 10]
    min_scaling = min_scalings[point // 7]
    read_targets = [25, 50, 100, 200, 400, 600, 900]
    read_target = read_targets[point % 7]
    weight = 10_000
    lc_weight = int(weight if weight >= 1 else 1)
    be_weight = int(1 if weight >= 1 else (1 // weight))

    # We focus on bandwidth here, so sacrifice latency, we do not need it as a sign of congestion as it complicates matters 
    qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 99.00, read_target, 95.00, 1_000_000, min_scaling, 150.00)
    model = cgroups.get_iocostmodel_from_nvme_model(nvme_device, False, 1)
    cgroups.set_iocost(model, qos)

    print(f"Using weight={lc_weight}/{be_weight} model_amplifier=1 read_target_us={read_target} min_scaling={min_scaling}%")
    exp_cgroups[0].ioweight = cgroups.IOWeight("default", lc_weight)
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].ioweight = cgroups.IOWeight("default", be_weight)

def setup_cgroups() -> list[cgroups.Cgroup]:
    lc_g = cgroups.create_cgroup(f"{EXPERIMENT_CGROUP_LC_PREAMBLE}.slice")
    be_g = cgroups.create_cgroup(f"{EXPERIMENT_CGROUP_BE_PREAMBLE}.slice")
    return [lc_g, be_g]

def setup_gjob(device_name: str) -> fio.FioGlobalJob:
    gjob = fio.FioGlobalJob()
    gjob.add_options([
        fio.TargetOption(device_name),
        fio.JobOption(fio.JobWorkload.RAN_READ),
        fio.DirectOption(True),
        fio.ThreadOption(False), # < we need to set this because ioprio is not transferred on fork (shocking I know)
        fio.SizeOption("100%"),
        fio.IOEngineOption(fio.IOEngine.LIBAIO), # <- when throttling iouring can die.
        fio.RequestSizeOption(f"{4 * 1024}"),
        fio.ConcurrentWorkerOption(1),
        fio.TimedOption('20s', '30s'),
        fio.AllowedCPUsOption(CORES),
    ])
    return gjob


def setup_sjobs(exp_cgroups: list[cgroups.Cgroup], numjobs: int) -> list[fio.FioSubJob]:
    # Create subjobs
    sjobs = []
    for i in range(numjobs):
        sjob_cgroup_path = f"{exp_cgroups[0].subpath if i == 0 else exp_cgroups[1].subpath}/fio-workload-{i}.service"
        # We need to create service group as well. 
        cgroups.create_cgroup_service(sjob_cgroup_path)

        sjob = fio.FioSubJob(f'j{i}')
        sjob.add_options([
            fio.CgroupOption(sjob_cgroup_path),
            fio.ConcurrentWorkerOption(1)
        ])
        sjobs.append(sjob)
    return sjobs

IO_KNOBS = {
    "none": IOKnob("none", 1, none_configure_cgroups),
    "bfq2": IOKnob("bfq2", 45, bfq2_configure_cgroups),
    "mq": IOKnob("mq", 27, mq_configure_cgroups),
    #"mq2": IOKnob("mq2", 27, mq2_configure_cgroups),
    "iomax": IOKnob("iomax", 45, iomax_configure_cgroups),
    "iolat": IOKnob("iolat", 45, iolat_configure_cgroups),
    "iocost": IOKnob("iocost", 45, iocost_configure_cgroups), # 54
    "iocost2": IOKnob("iocost2", 35, iocost2_configure_cgroups),
    "iocost3": IOKnob("iocost3", 35, iocost3_configure_cgroups),
}

def tapps_job(sjob, i):
    if i == 0:
        return sjob 

    qoption =  fio.QDOption(256)
    sjob.add_options([
        qoption
    ])
    return sjob

def tapps_job_joined(sjob, i):
    qoption =  fio.QDOption(256)
    sjob.add_options([
        qoption
    ])
    return sjob

def rq_job(sjob, i):
    if i == 0:
        return sjob 
    soption = fio.RequestSizeOption(["4096", f"{1024 * 128}"][i % 2])
    qoption =  fio.QDOption(256)
    sjob.add_options([
        qoption,
        soption
    ])
    return sjob

def rq_job_joined(sjob, i):
    soption = fio.RequestSizeOption(["4096", f"{1024 * 128}"][i % 2])
    qoption =  fio.QDOption(256)
    sjob.add_options([
        qoption,
        soption
    ])
    return sjob

def access_job(sjob, i):
    if i == 0:
        return sjob 
    joption = fio.JobOption([fio.JobWorkload.RAN_READ, fio.JobWorkload.SEQ_READ][i%2])
    qoption =  fio.QDOption(256)
    sjob.add_options([
        qoption,
        joption
    ])
    return sjob

def access_job_joined(sjob, i):
    joption = fio.JobOption([fio.JobWorkload.RAN_READ, fio.JobWorkload.SEQ_READ][i%2])
    qoption =  fio.QDOption(256)
    sjob.add_options([
        qoption,
        joption
    ])
    return sjob

def rw_short_job(sjob, i):
    if i == 0:
        return sjob 
    joption = fio.JobOption([fio.JobWorkload.RAN_READ, fio.JobWorkload.MIXED][i%2])
    qoption =  fio.QDOption(256)
    sjob.add_options([
        qoption,
        joption
    ])
    
    if i%2 == 1:
        moption = fio.RWMixRatioOption("75")
        sjob.add_options([
            moption
        ])
    return sjob

def rw_short_job_joined(sjob, i):
    joption = fio.JobOption([fio.JobWorkload.RAN_READ, fio.JobWorkload.MIXED][i%2])
    qoption =  fio.QDOption(256)
    sjob.add_options([
        qoption,
        joption
    ])

    if i%2 == 1:
        moption = fio.RWMixRatioOption("75")
        sjob.add_options([
            moption
        ])
    return sjob

def rw_long_job(sjob, i):
    toption = fio.TimedOption('20s', '10m')
    if i == 0:
        sjob.add_options([
            toption
        ])
        return sjob 
    joption = fio.JobOption([fio.JobWorkload.RAN_READ, fio.JobWorkload.RAN_WRITE][i%2])
    qoption =  fio.QDOption(256)
    sjob.add_options([
        qoption,
        joption,
        toption
    ])
    return sjob

def rw_long_job_joined(sjob, i):
    toption = fio.TimedOption('20s', '10m')
    joption = fio.JobOption([fio.JobWorkload.RAN_READ, fio.JobWorkload.RAN_WRITE][i%2])
    qoption =  fio.QDOption(256)
    sjob.add_options([
        qoption,
        joption,
        toption
    ])
    return sjob

EXPERIMENTS = {
    # General random read
    "tapps": Experiment("tapps", tapps_job),
    "tapps_joined": Experiment("tapps_joined", tapps_job_joined),
    # RQ-size
    "rq": Experiment("rq", rq_job),
    "rq_joined": Experiment("rq_joined", rq_job_joined),
    # Access pattern
    "access": Experiment("access", access_job),
    "access_joined": Experiment("access_joined", access_job_joined), 
    # short rw
    "rwshort": Experiment("rwshort", rw_short_job),
    "rwshort_joined": Experiment("rwshort_joined", rw_short_job_joined),
    # GC
    "rwlong": Experiment("rwlong", rw_long_job),
    "rwlong_joined": Experiment("rwlong_joined", rw_long_job),
}

def find_isolation(knobs_to_test: list[IOKnob]):
    nvme_device = get_nvmedev()
    outdir = f'./out/{nvme_device.eui}'
    os.makedirs(outdir, exist_ok = True)
    os.makedirs(f'./tmp', exist_ok = True)

    exp_cgroups = setup_cgroups()

    for knob in knobs_to_test:
        # Preamble
        cgroups.disable_iocontrol_with_groups(exp_cgroups)
        del nvme_device.io_scheduler
        knob.configure_cgroups(nvme_device, exp_cgroups, (1024 * 1024 * 1024 * 10), [1])
        for group in exp_cgroups:
            group.force_cpuset_cpus(CORES)

        print(f"Finding isolation point for {knob.name}")
        get_singleknob_bw(knob, nvme_device, exp_cgroups, True)

    # Disable
    cgroups.disable_iocontrol_with_groups(exp_cgroups)
    del nvme_device.io_scheduler
    for group in exp_cgroups:
        group.force_cpuset_cpus('')

def run_experiment(experiment: Experiment, knobs_to_test: list[IOKnob], nvme_device: nvme.NVMeDevice, exp_cgroups):
    job_gen = fio.FioJobGenerator(True)
    job_runner = fio.FioRunner('sudo ../dependencies/fio/fio', fio.FioRunnerOptions(overwrite=True, parse_only=False))
    outdir = f'./out/{nvme_device.eui}'

    for knob in knobs_to_test: 
        print(f"___________________________________")
        print(f"Experiment [ {experiment.name} -- {knob.name}]") 
        print(f"___________________________________")

        if CONFIG_POINT_FORCED:
            print(f"Overwriting config_point range [0--{knob.points}] with [{CONFIG_POINT}]")
            config_points = [CONFIG_POINT]
        else:
            config_points = range(knob.points)
        for config_point in config_points:
            try:
                print(f"Configuring experiment [{experiment.name}, {config_point}/{knob.points}] on {nvme_device.syspath}")        
                cgroups.disable_iocontrol_with_groups(exp_cgroups)
                del nvme_device.io_scheduler
                
                for group in exp_cgroups:
                    group.force_cpuset_cpus(CORES)
                knob.configure_cgroups(nvme_device, exp_cgroups, config_point)

                print(f"Generating experiment [numjobs={NUMJOBS}]")         

                gjob = setup_gjob(nvme_device.syspath)
                gjob.add_options([
                    fio.GroupReportingOption(False),
                ])
                for i, app in enumerate(setup_sjobs(exp_cgroups, NUMJOBS)):
                    app = experiment.change_jobs(app, i)              
                    gjob.add_job(app) 
                    # .
                    sjob_cgroup_path = f"{exp_cgroups[0].subpath if i == 0 else exp_cgroups[1].subpath}/fio-workload-{i}.service"
                    cgroups.create_cgroup_service(sjob_cgroup_path)
                job_gen.generate_job_file(f'./tmp/{experiment.name}-{knob.name}-{NUMJOBS}', gjob)

                print(f"Running experiment [experiment={experiment.name}]")                    

                fioproc = job_runner.run_job_deferred(\
                    f'./tmp/{experiment.name}-{knob.name}-{NUMJOBS}',\
                    f'./{outdir}/{experiment.name}-{knob.name}-{NUMJOBS}-{config_point}.json')
                fioproc.wait()

                with open(f'./{outdir}/{experiment.name}-{knob.name}-{NUMJOBS}-{config_point}.json', 'r') as f:
                    js = json.load(f)
                    bws = [float(j['read']['bw_mean']) + float(j['write']['bw_mean'])for j in js['jobs']]
                    bwsum = sum(bws) / (1024 * 1024)
                    bw1 = bws[0] / (1024 * 1023) 
                    p99 = js['jobs'][0]['read']['clat_ns']['percentile']['99.000000'] / 1000
                    print(f"LC-app achieved {p99}us @ {bw1} GiB/s. Aggregated BW of all workloads is {bwsum} GiB/s")

                # Cleaning up
                if not nvme_device.isoptane and "rw" in experiment.name:
                    print("Resetting device state by preconditioning")
                    nvme_format(nvme_device)
                    fioproc = job_runner.run_job_deferred(\
                        f'./precondition.fio',\
                        f'./out/{experiment.name}-precond.json',
                        fio_extra_opts=[f"filename={nvme_device.syspath}"])
                    fioproc.wait()
                    print("Done preconditioning")
            
            # Cleanup
            except KeyboardInterrupt:
                print("Trying to exit gracefully")
                return
            except:
                print(f"Failed {experiment.name} - {knob.name} {config_point}/{knob.points}")

def run_experiments(experiments_to_run: list[Experiment], knobs_to_test: list[IOKnob]):
    nvme_device = get_nvmedev()
    outdir = f'./out/{nvme_device.eui}'
    os.makedirs(outdir, exist_ok = True)
    os.makedirs(f'./tmp', exist_ok = True)

    exp_cgroups = setup_cgroups()

    # Run
    for experiment in experiments_to_run:
        run_experiment(experiment, knobs_to_test, nvme_device, exp_cgroups)
   
    # Reset
    for group in exp_cgroups:
        group.force_cpuset_cpus('')
    cgroups.disable_iocontrol_with_groups(exp_cgroups)

if __name__ == "__main__":
    if not check_kernel_requirements():
      print("The kernel does not meet the necessary requirements, please check README.md")
      exit(1)

    parser = argparse.ArgumentParser(
        description="Fairness experiments for all io.knobs"
    )
    # Saturation
    parser.add_argument(f"--isolation", type=bool, required=False, default=False)
    # Shortcut
    parser.add_argument(f"--numjobs", type=int, required=False, default=0)
    parser.add_argument(f"--configpoint", type=int, required=False, default=-1)
    # cgroups
    for key in IO_KNOBS.keys():
        parser.add_argument(f"--{key}", type=bool, required=False, default=False)
    for key in EXPERIMENTS.keys():
        parser.add_argument(f"--{key}", type=bool, required=False, default=False)
    args = parser.parse_args()

    # Determine knobs to test
    knobs_to_test = []
    experiments_to_run = []
    isol = False
    for arg, val in vars(args).items():
        if arg == "isolation":
            isol = val
        elif arg == "numjobs" and val > 0:
            NUMJOBS = val
        elif arg == "configpoint" and val >= 0:
            CONFIG_POINT_FORCED = True
            CONFIG_POINT = val
        elif arg in IO_KNOBS and val:
            knobs_to_test.append(IO_KNOBS[arg])
        elif arg in EXPERIMENTS and val:
            experiments_to_run.append(EXPERIMENTS[arg])
    
    # Find latency in isolation
    if isol:
        if not len(knobs_to_test):
            knobs_to_test = list(IO_KNOBS.values())
        find_isolation(knobs_to_test)
    # Normal experiment
    else:
        if not len(experiments_to_run):
            experiments_to_run = list(EXPERIMENTS.values())
        if not len(knobs_to_test):
            knobs_to_test = list(IO_KNOBS.values())
        run_experiments(experiments_to_run, knobs_to_test)
