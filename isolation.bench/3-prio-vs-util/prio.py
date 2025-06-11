
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

EXPERIMENT_CGROUP_PATH_PREAMBLE=f"example-workload"
EXPERIMENT_MAX_TENANT_COUNT=256

CORES = '1-10'
NUMJOBS = 8 # + 1 # +1 to force 1 LC-tenants

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
    p = o[point]

    exp_cgroups[0].ioprio = p[0]
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].ioprio = p[1]

def iomax_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], max_bw, weights):
    total_weight = sum(weights) 

    major_minor = nvme_device.major_minor
    for index, group in enumerate(exp_cgroups):
        if index >= len(weights):
            break
        weight = weights[index] / total_weight
        group.iomax = cgroups.IOMax(major_minor, int(weight * max_bw), int(weight * max_bw), 10_000_000, 10_000_000)

def bfq2_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], point: int):
    nvme_device.io_scheduler = nvme.IOScheduler.BFQ
    nvme_device.set_ioscheduler_parameter("low_latency", "0")
    nvme_device.set_ioscheduler_parameter("slice_idle", "1")

    weights = [1, 2, 5, 10, 100, 1000]

    exp_cgroups[0].iobfqweight = cgroups.IOBFQWeight("default", weights[point])
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].iobfqweight = cgroups.IOBFQWeight("default", 1)


def iolat_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], point: int):
    major_minor = nvme_device.major_minor

    lats = [10, 70, 100, 200, 100]
    exp_cgroups[0].iolatency = cgroups.IOLatency(major_minor, lats[point])

def iocost_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], point: int):
    read_targets = [1_000_000, 1_000, 100, 50, 10]
    read_target =  read_targets[4 - (point // 7)]  

    # We focus on bandwidth here, so sacrifice latency, we do not need it as a sign of congestion as it complicates matters 
    qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 99.00, read_target, 95.00, 1_000_000, 50.00, 150.00)
    model = cgroups.get_iocostmodel_from_nvme_model(nvme_device, False)
    cgroups.set_iocost(model, qos)

    weights = [1, 2, 5, 10, 100, 1000, 10000]

    exp_cgroups[0].ioweight = cgroups.IOWeight("default", weights[point])
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].ioweight = cgroups.IOWeight("default", 1)

def setup_cgroups() -> list[cgroups.Cgroup]:
    return [cgroups.create_cgroup(f"{EXPERIMENT_CGROUP_PATH_PREAMBLE}-{i}.slice") for i in range(0,EXPERIMENT_MAX_TENANT_COUNT)]

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
        fio.TimedOption('20s', '60s'),
        fio.AllowedCPUsOption(CORES),
    ])
    return gjob


def setup_sjobs(exp_cgroups: list[cgroups.Cgroup], numjobs: int) -> list[fio.FioSubJob]:
    # Create subjobs
    sjobs = []
    for i in range(numjobs):
        sjob_cgroup_path = f"{exp_cgroups[i].subpath}/fio-workload.service"
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
    "bfq2": IOKnob("bfq2", 6, bfq2_configure_cgroups),
    "mq": IOKnob("mq", 9, mq_configure_cgroups),
    "iomax": IOKnob("iomax", 0, iomax_configure_cgroups),
    "iolat": IOKnob("iolat", 5, iolat_configure_cgroups),
    "iocost": IOKnob("iocost", 35, iocost_configure_cgroups),
}

def tapps_job(sjob, i):
    if i == 0:
        return sjob 

    qoption =  fio.QDOption(256)
    sjob.add_options([
        qoption
    ])
    return sjob

EXPERIMENTS = {
    # General random read
    "tapps": Experiment("tapps", tapps_job),
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

        for config_point in range(knob.points):

            print(f"Configuring experiment [{experiment.name}, {config_point}] on {nvme_device.syspath}")        
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
                sjob_cgroup_path = f"{exp_cgroups[i].subpath}/fio-workload.service"
                cgroups.create_cgroup_service(sjob_cgroup_path)
            job_gen.generate_job_file(f'./tmp/{experiment.name}-{knob.name}-{NUMJOBS}', gjob)

            print(f"Running experiment [experiment={experiment.name}]")                    

            fioproc = job_runner.run_job_deferred(\
                f'./tmp/{experiment.name}-{knob.name}-{NUMJOBS}',\
                f'./{outdir}/{experiment.name}-{knob.name}-{NUMJOBS}-{config_point}.json')
            fioproc.wait()


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
