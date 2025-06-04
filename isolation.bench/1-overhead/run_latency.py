import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'util')))

from dataclasses import dataclass
from typing import Callable
import argparse

import fio
from util_sysfs import cgroups as cgroups
from util_sysfs import nvme as nvme
from util_sysfs.bench import *

EXPERIMENT_CGROUP_PATH_PREAMBLE=f"example-workload"
EXPERIMENT_MAX_TENANT_COUNT=256
NUMJOBS = [2**i for i in range(0,9)]

@dataclass
class IOKnob:
    name: str
    configure_cgroups_active: Callable[[nvme.NVMeDevice, list[cgroups.Cgroup]], None]
    configure_cgroups_inactive: Callable[[nvme.NVMeDevice, list[cgroups.Cgroup]], None]

def none_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    pass

def iomax_active_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    major_minor = nvme_device.major_minor
    for group in exp_cgroups:
        group.iomax = cgroups.IOMax(major_minor, 1024 * 1024 * 500, 1024 * 1024 * 500, 1_000_000, 1_000_000)

def iomax_inactive_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    major_minor = nvme_device.major_minor
    for group in exp_cgroups:
        group.iomax = cgroups.IOMax(major_minor, 1024 * 1024 * 5000, 1024 * 1024 * 5000, 10_000_000, 10_000_000)

def bfq_active_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    nvme_device.io_scheduler = nvme.IOScheduler.BFQ

def mq_active_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    nvme_device.io_scheduler = nvme.IOScheduler.MQ_DEADLINE

def iolat_active_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    major_minor = nvme_device.major_minor
    for group in exp_cgroups:
        group.iolatency = cgroups.IOLatency(major_minor, 10)   

def iolat_inactive_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    major_minor = nvme_device.major_minor
    for group in exp_cgroups:
        group.iolatency = cgroups.IOLatency(major_minor, 1000000)

def iocost_active_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    model = cgroups.IOCostModel(nvme_device.major_minor, 'user', 'linear', 2706339840, 89698, 110036, 1063126016, 135560, 130734)
    qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 95.00, 1000000, 95.00, 1000000, 50.00, 150.00)

def iocost_inactive_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    model = cgroups.IOCostModel(nvme_device.major_minor, 'user', 'linear', 2706339840*10, 89698*10, 110036*10, 1063126016*10, 135560*10, 130734*10)
    qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 95.00, 1000000, 95.00, 1000000, 50.00, 150.00)

def setup_cgroups() -> list[cgroups.Cgroup]:
    return [cgroups.create_cgroup(f"{EXPERIMENT_CGROUP_PATH_PREAMBLE}-{i}.slice") for i in range(0,EXPERIMENT_MAX_TENANT_COUNT)]

def setup_jobs(device_name: str, exp_cgroups: list[cgroups.Cgroup], numjobs: int, cgroups_active: bool) -> fio.FioGlobalJob:
    job = fio.FioGlobalJob()
    job.add_options([
        fio.TargetOption(device_name),
        fio.JobOption(fio.JobWorkload.RAN_READ),
        fio.DirectOption(True),
        fio.GroupReportingOption(True),
        fio.ThreadOption(False), # < we need to set this because ioprio is not transferred on fork (shocking I know)
        fio.ExtraHighTailLatencyOption(),
        fio.SizeOption("100%"),
        fio.IOEngineOption(fio.IOEngine.IO_URING),
        fio.Io_uringFixedBufsOption(True),
        fio.Io_uringRegisterFilesOption(True),
        fio.QDOption(1),
        fio.RequestSizeOption(f"{4 * 1024}"),
        fio.ConcurrentWorkerOption(1),
        fio.TimedOption('20s', '60s'),
        fio.AllowedCPUsOption('2'),
    ])   

    for i in range(numjobs if cgroups_active else 1):
        sjob_cgroup_path = f"{exp_cgroups[i].subpath}/fio-workload.service" if cgroups_active else f"{exp_cgroups[0].subpath}/fio-workload.service"
        # We need to create service group as well. 
        cgroups.create_cgroup_service(sjob_cgroup_path)

        sjob = fio.FioSubJob(f'j{i}')
        sjob.add_options([
            fio.CgroupOption(sjob_cgroup_path),
            fio.ConcurrentWorkerOption(1 if cgroups_active else numjobs)
        ])
        job.add_job(sjob)
    return job

IO_KNOBS = {
    "none": IOKnob("none", none_configure_cgroups, none_configure_cgroups),
    "bfq": IOKnob("bfq", bfq_active_configure_cgroups, bfq_active_configure_cgroups),
    "mq": IOKnob("mq", mq_active_configure_cgroups, mq_active_configure_cgroups),
    "iomax": IOKnob("iomax", iomax_active_configure_cgroups, iomax_inactive_configure_cgroups),
    "iolat": IOKnob("iolat", iolat_active_configure_cgroups, iolat_inactive_configure_cgroups),
    "iocost": IOKnob("iocost", iocost_active_configure_cgroups, iocost_inactive_configure_cgroups),
}

def main(knobs_to_test: list[IOKnob], active: bool, cgroups_active: bool):
    nvme_device = get_nvmedev()
    outdir = f'./out/{nvme_device.eui}'
    try:
        os.mkdir(outdir)
    except:
        pass
    exp_cgroups = setup_cgroups()
    job_gen = fio.FioJobGenerator(True)
    job_runner = fio.FioRunner('sudo ../dependencies/fio/fio', fio.FioRunnerOptions(overwrite=True, parse_only=False))

    original_nvme_scheduler = nvme_device.io_scheduler
    for knob in knobs_to_test: 
        print(f"___________________________________")
        print(f"Experiment [{knob.name} -- {active}]") 
        print(f"___________________________________")

        print(f"Configuring experiment [active={active}]")        
        cgroups.disable_iocontrol_with_groups(exp_cgroups)
        del nvme_device.io_scheduler
        if active:
            knob.configure_cgroups_active(nvme_device, exp_cgroups)
        else:
            knob.configure_cgroups_inactive(nvme_device, exp_cgroups)

        for group in exp_cgroups:
            group.force_cpuset_cpus('2')

        try:
            os.mkdir(f'./tmp/{knob.name}')
            os.mkdir(f'./out/{nvme_device.eui}/{knob.name}')
        except:
            pass

        for numjobs in NUMJOBS:
            print(f"Generating experiment [numjobs={numjobs}]")        
            job = setup_jobs(nvme_device.syspath, exp_cgroups, numjobs, cgroups_active)
            job_gen.generate_job_file(f'./tmp/{knob.name}/{numjobs}-{cgroups_active}', job)

            print(f"Running experiment [numjobs={numjobs}]")        
            fioproc = job_runner.run_job_deferred(f'./tmp/{knob.name}/{numjobs}-{cgroups_active}', f'./{outdir}/{knob.name}/{active}-{numjobs}-{cgroups_active}.json')
            do_sleep(10)
            pidstat = start_pidstat(f'./{outdir}/{knob.name}/{active}-{numjobs}-{cgroups_active}.pidstat', '10')            
            sar = start_sar(f'./{outdir}/{knob.name}/{active}-{numjobs}-{cgroups_active}.sar', '1-15')            
            fioproc.wait()
            pidstat.terminate()
            pidstat.wait()
            kill_sar()
            sar.wait()

        for group in exp_cgroups:
            group.force_cpuset_cpus('')
    cgroups.disable_iocontrol_with_groups(exp_cgroups)
    nvme_device.io_scheduler = original_nvme_scheduler

if __name__ == "__main__":
    if not check_kernel_requirements():
      print("The kernel does not meet the necessary requirements, please check README.md")
      exit(1)

    parser = argparse.ArgumentParser(
        description="Example experiments for all io.knobs"
    )
    parser.add_argument(f"--active", type=bool, required=False, default=False)
    parser.add_argument(f"--cgroups", type=bool, required=False, default=False)
    for key in IO_KNOBS.keys():
        parser.add_argument(f"--{key}", type=bool, required=False, default=False)
    args = parser.parse_args()

    # Determine knobs to test
    knobs_to_test = []
    active = False
    cgroups_active = False
    for arg, val in vars(args).items():
        if arg not in IO_KNOBS and arg != "active" and arg != "cgroups":
            raise ValueError(f"Knob {arg} not known")
        elif arg == "active":
            active = val 
        elif arg == "cgroups":
            cgroups_active = val 
        elif val:
            knobs_to_test.append(IO_KNOBS[arg])

    if not len(knobs_to_test):
        knobs_to_test = list(IO_KNOBS.values())

    main(knobs_to_test, active, cgroups_active)

