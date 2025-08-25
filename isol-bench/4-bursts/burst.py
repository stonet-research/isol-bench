# Latency, set very low target for L-app, 
# iocost set very high prio
# iomax, set low target
# BFQ high prio
# MQ RT and other idle

# evaluate for 100us -- 5s

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
EXPERIMENT_CGROUP_BE_PREAMBLE=f"burst-workload"
EXPERIMENT_CGROUP_PATH_PREAMBLE=f"example-workload"
EXPERIMENT_MAX_TENANT_COUNT=256

CORES = '1-10'
NUMJOBS = 4 + 1 # +1 to force 1 LC-tenants
CONFIG_POINT_FORCED = False
CONFIG_POINT = 0

@dataclass
class IOKnob:
    name: str
    configure_cgroups: Callable[[nvme.NVMeDevice, list[cgroups.Cgroup]], None]

def none_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    return "none"

def mq_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    nvme_device.io_scheduler = nvme.IOScheduler.MQ_DEADLINE

    exp_cgroups[0].ioprio = cgroups.IOPriorityClass.RESTRICT_TO_BE
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].ioprio = cgroups.IOPriorityClass.IDLE

def iomax_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].iomax = cgroups.IOMax(nvme_device.major_minor, int(1024 * 1024 * 1024), int(1024 * 1024 * 1024), 10_000_000, 10_000_000)

def bfq2_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    nvme_device.io_scheduler = nvme.IOScheduler.BFQ
    nvme_device.set_ioscheduler_parameter("low_latency", "0")
    nvme_device.set_ioscheduler_parameter("slice_idle", "1")

    exp_cgroups[0].iobfqweight = cgroups.IOBFQWeight("default", 1_000)
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].iobfqweight = cgroups.IOBFQWeight("default", 1)

def iolat_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    exp_cgroups[0].iolatency = cgroups.IOLatency(nvme_device.major_minor, 10)

def iocost_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    min_scaling = 25 
    model_amplifier = 1
    read_target = 15

    # We focus on bandwidth here, so sacrifice latency, we do not need it as a sign of congestion as it complicates matters 
    qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 99.00, read_target, 95.00, 1_000_000, min_scaling, 150.00)
    model = cgroups.get_iocostmodel_from_nvme_model(nvme_device, False, model_amplifier)
    cgroups.set_iocost(model, qos)

    exp_cgroups[0].ioweight = cgroups.IOWeight("default", 10_000)
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].ioweight = cgroups.IOWeight("default", 1)

def iocost2_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    min_scaling = 75 
    model_amplifier = 1
    read_target = 1_000_000

    # We focus on bandwidth here, so sacrifice latency, we do not need it as a sign of congestion as it complicates matters 
    qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 99.00, read_target, 95.00, 1_000_000, min_scaling, 150.00)
    model = cgroups.get_iocostmodel_from_nvme_model(nvme_device, False, model_amplifier)
    cgroups.set_iocost(model, qos)

    exp_cgroups[0].ioweight = cgroups.IOWeight("default", 10_000)
    for i in range(1, len(exp_cgroups)):
        exp_cgroups[i].ioweight = cgroups.IOWeight("default", 1)

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
        fio.AllowedCPUsOption(CORES),
    ])
    return gjob

def setup_lcjob(exp_cgroups: list[cgroups.Cgroup], delay, runtime):
    sjob_cgroup_path = f"{exp_cgroups[0].subpath}/fio-workload-0.service"
    # We need to create service group as well. 
    cgroups.create_cgroup_service(sjob_cgroup_path)

    sjob = fio.FioSubJob(f'lc')
    sjob.add_options([
        fio.CgroupOption(sjob_cgroup_path),
        fio.ConcurrentWorkerOption(1),
        fio.DelayOption(delay),
        fio.TimedOption('0s', runtime),
    ])
    return sjob

def setup_bejobs(exp_cgroups: list[cgroups.Cgroup], numjobs, runtime):
    # Create subjobs
    sjobs = []
    for i in range(1, numjobs):
        sjob_cgroup_path = f"{exp_cgroups[1].subpath}/fio-workload-{i}.service"
        # We need to create service group as well. 
        cgroups.create_cgroup_service(sjob_cgroup_path)

        sjob = fio.FioSubJob(f'j{i}')
        sjob.add_options([
            fio.CgroupOption(sjob_cgroup_path),
            fio.ConcurrentWorkerOption(1),
            fio.QDOption(256),
            fio.TimedOption('0s', runtime),
        ])
        sjobs.append(sjob)
    return sjobs

IO_KNOBS = {
    "none": IOKnob("none", none_configure_cgroups),
    "bfq2": IOKnob("bfq2", bfq2_configure_cgroups),
    "mq": IOKnob("mq", mq_configure_cgroups),
    "iomax": IOKnob("iomax", iomax_configure_cgroups),
    "iolat": IOKnob("iolat",  iolat_configure_cgroups),
    "iocost": IOKnob("iocost", iocost_configure_cgroups), # 54
    "iocost2": IOKnob("iocost2", iocost2_configure_cgroups), # 54
}

def run_experiment(knobs_to_test: list[IOKnob], nvme_device: nvme.NVMeDevice, exp_cgroups, workload):
    job_gen = fio.FioJobGenerator(True)
    job_runner = fio.FioRunner('sudo ../dependencies/fio/fio', fio.FioRunnerOptions(overwrite=True, parse_only=False))
    outdir = f'./out/{nvme_device.eui}'

    for knob in knobs_to_test: 
        print(f"___________________________________")
        print(f"{knob.name} [{workload}]") 
        print(f"___________________________________")

        for runtime in ["10s"]:
            print(f"Configuring {knob.name} [{workload} @ {runtime}] on {nvme_device.syspath}")        
            cgroups.disable_iocontrol_with_groups(exp_cgroups)
            del nvme_device.io_scheduler
            
            for group in exp_cgroups:
                group.force_cpuset_cpus(CORES)
            knob.configure_cgroups(nvme_device, exp_cgroups)

            print(f"Generating experiment [numjobs={NUMJOBS} runtime={runtime}]")         

            gjob = setup_gjob(nvme_device.syspath)
            gjob.add_options([
                fio.GroupReportingOption(False),
            ])
        
            # Setup LC-job
            lc_job = setup_lcjob(exp_cgroups, '60s', runtime)
            if workload == "batch":
                lc_job.add_options([
                    fio.QDOption("256"),
                    fio.BWShortLog(f"./{outdir}/{knob.name}")
                ])
            else:
                lc_job.add_options([
                    fio.LatencyLog(f"./{outdir}/{knob.name}")
                ])
            gjob.add_job(lc_job)
            # Setup BE-jobs
            be_jobs = setup_bejobs(exp_cgroups, NUMJOBS, '80s')
            for be_job in be_jobs:
                gjob.add_job(be_job) 
            job_gen.generate_job_file(f'./tmp/{knob.name}-{workload}-{runtime}-{NUMJOBS}', gjob)

            print(f"Running experiment")                    

            fioproc = job_runner.run_job_deferred(\
                f'./tmp/{knob.name}-{workload}-{runtime}-{NUMJOBS}',\
                f'./{outdir}/{knob.name}-{workload}-{runtime}-{NUMJOBS}.json')
            fioproc.wait()

            with open(f'./{outdir}/{knob.name}-{workload}-{runtime}-{NUMJOBS}.json', 'r') as f:
                js = json.load(f)
                bws = [float(j['read']['bw_mean']) + float(j['write']['bw_mean'])for j in js['jobs'][1:]]
                if workload == "batch":
                    bw = js['jobs'][0]['read']['bw_mean'] / (1024 * 1024)
                    print(f"--->    Batch-app achieved {bw} GiB/s (BEs achieved {sum(bws) / (1024 * 1024)} GiB/s)")
                else:
                    p99 = js['jobs'][0]['read']['clat_ns']['percentile']['99.000000'] / 1000
                    print(f"--->    LC-app achieved {p99}us (BEs achieved {sum(bws) / (1024 * 1024)} GiB/s)")


def run_experiments(knobs_to_test: list[IOKnob], workload):
    nvme_device = get_nvmedev()
    outdir = f'./out/{nvme_device.eui}'
    os.makedirs(outdir, exist_ok = True)
    os.makedirs(f'./tmp', exist_ok = True)

    exp_cgroups = setup_cgroups()

    # Run
    run_experiment(knobs_to_test, nvme_device, exp_cgroups, workload)
   
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
    # Shortcut
    parser.add_argument(f"--numjobs", type=int, required=False, default=0)
    # Workload
    parser.add_argument(f"--workload", type=str, required=False, default="lc")
    # cgroups
    for key in IO_KNOBS.keys():
        parser.add_argument(f"--{key}", type=bool, required=False, default=False)
    args = parser.parse_args()

    # Determine knobs to test
    knobs_to_test = []
    isol = False
    workload = "lc"
    for arg, val in vars(args).items():
        if arg == "numjobs" and val > 0:
            NUMJOBS = val
        elif arg in IO_KNOBS and val:
            knobs_to_test.append(IO_KNOBS[arg])
        elif arg == "workload":
            workload = val

    if not len(knobs_to_test):
        knobs_to_test = list(IO_KNOBS.values())
    run_experiments(knobs_to_test, workload)
