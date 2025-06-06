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
from util_sysfs.perf import *

EXPERIMENT_CGROUP_PATH_PREAMBLE=f"example-workload"
EXPERIMENT_MAX_TENANT_COUNT=256

CORES = '1-10'
NUMJOBS = [1, 3, 5, 7, 9, 11, 13, 15, 17]
NUMDISKS = [1, 2, 4, 7]

@dataclass
class IOKnob:
    name: str
    configure_cgroups: Callable[[nvme.NVMeDevice, list[cgroups.Cgroup]], None]

def none_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    pass

def iomax_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    major_minor = nvme_device.major_minor
    for group in exp_cgroups:
        group.iomax = cgroups.IOMax(major_minor, 1024 * 1024 * 5000, 1024 * 1024 * 5000, 10_000_000, 10_000_000)
        #group.iomax = cgroups.IOMax(major_minor, 1024 * 1024 * 100, 1024 * 1024 * 100, 10_000, 10_000)

def bfq_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    nvme_device.io_scheduler = nvme.IOScheduler.BFQ

def mq_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    nvme_device.io_scheduler = nvme.IOScheduler.MQ_DEADLINE

def iolat_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    major_minor = nvme_device.major_minor
    for group in exp_cgroups:
        group.iolatency = cgroups.IOLatency(major_minor, 1000000)
        group.iolatency = cgroups.IOLatency(major_minor, 10)

def iocost_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    model = cgroups.IOCostModel(nvme_device.major_minor, 'user', 'linear', 1024*1024*1024*10, 10_000_000, 10_000_000, 1024*1024*1024*10, 10_000_000, 10_000_000)
    # model = cgroups.IOCostModel(nvme_device.major_minor, 'user', 'linear', 2706339840//100, 89698//100, 110036//100, 1063126016//100, 135560//100, 130734//100)
    qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 95.00, 1_000_000, 95.00, 1_000_000, 50.00, 150.00)
    #qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 95.00, 100, 95.00, 100, 50.00, 150.00)
    cgroups.set_iocost(model, qos)

def setup_cgroups() -> list[cgroups.Cgroup]:
    return [cgroups.create_cgroup(f"{EXPERIMENT_CGROUP_PATH_PREAMBLE}-{i}.slice") for i in range(0,EXPERIMENT_MAX_TENANT_COUNT)]

def setup_jobs(device_names: list[str], exp_cgroups: list[cgroups.Cgroup], numjobs: int, cgroups_active: bool) -> fio.FioGlobalJob:
    # Parse string
    device_str = ':'.join(device_names)
    print(device_str, device_names)

    # Create shared options
    job = fio.FioGlobalJob()
    job.add_options([
        fio.TargetOption(device_str),
        fio.JobOption(fio.JobWorkload.RAN_READ),
        fio.DirectOption(True),
        fio.GroupReportingOption(True),
        fio.ThreadOption(False), # < we need to set this because ioprio is not transferred on fork (shocking I know)
        fio.ExtraHighTailLatencyOption(),
        fio.SizeOption("100%"),
        fio.IOEngineOption(fio.IOEngine.IO_URING),
        fio.Io_uringFixedBufsOption(True),
        fio.Io_uringRegisterFilesOption(True),
        fio.QDOption(256),
        fio.RequestSizeOption(f"{4 * 1024}"),
        fio.ConcurrentWorkerOption(1),
        fio.TimedOption('20s', '60s'),
        fio.AllowedCPUsOption(CORES),
    ])   

    # Create subjobs
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
    "none": IOKnob("none", none_configure_cgroups),
    "bfq": IOKnob("bfq", bfq_configure_cgroups),
    "mq": IOKnob("mq", mq_configure_cgroups),
    "iomax": IOKnob("iomax", iomax_configure_cgroups),
    "iolat": IOKnob("iolat", iolat_configure_cgroups),
    "iocost": IOKnob("iocost", iocost_configure_cgroups),
}

def main(knobs_to_test: list[IOKnob], cgroups_active: bool):
    nvme_devices = nvme_list()
    outdir = f'./out/nvmescaling'
    try:
        os.mkdir(outdir)
    except:
        pass
    exp_cgroups = setup_cgroups()
    job_gen = fio.FioJobGenerator(True)
    job_runner = fio.FioRunner('sudo ../dependencies/fio/fio', fio.FioRunnerOptions(overwrite=True, parse_only=False))

    for knob in knobs_to_test: 
        print(f"___________________________________")
        print(f"Experiment [{knob.name}]") 
        print(f"___________________________________")

        print(f"Configuring experiment")        
        cgroups.disable_iocontrol_with_groups(exp_cgroups)
        for nvme_device in nvme_devices:
            del nvme_device.io_scheduler
            knob.configure_cgroups(nvme_device, exp_cgroups)

        for group in exp_cgroups:
            group.force_cpuset_cpus(CORES)

        os.makedirs(f'./tmp/{knob.name}', exist_ok = True)
        os.makedirs(f'./out/nvmescaling/{knob.name}', exist_ok = True)

        # We do in reverse so we can kill "early"
        for device_count in NUMDISKS[::-1]:
            for numjobs in NUMJOBS[::-1]:
                print(f"Generating experiment [device_count={device_count}/[{NUMDISKS}] numjobs={numjobs}]")        
                device_paths = [nvme_device.syspath for nvme_device in nvme_devices[0:device_count]]
                job = setup_jobs(device_paths, exp_cgroups, numjobs, cgroups_active)
                job_gen.generate_job_file(f'./tmp/{knob.name}/t-{device_count}-{numjobs}-{cgroups_active}', job)

                print(f"Running experiment [device_count={device_count} numjobs={numjobs}]")                    

                fioproc = job_runner.run_job_deferred(f'./tmp/{knob.name}/t-{device_count}-{numjobs}-{cgroups_active}', f'./{outdir}/{knob.name}/t-{device_count}-{numjobs}-{cgroups_active}.json')
                do_sleep(10)
                pidstat = start_pidstat(f'./{outdir}/{knob.name}/t-{device_count}-{numjobs}-{cgroups_active}.pidstat', '11')            
                sar = start_sar(f'./{outdir}/{knob.name}/t-{device_count}-{numjobs}-{cgroups_active}.sar', '1-15')            
                fioproc.wait()
                pidstat.terminate()
                pidstat.wait()
                kill_sar()
                sar.wait()

        for group in exp_cgroups:
            group.force_cpuset_cpus('')
    cgroups.disable_iocontrol_with_groups(exp_cgroups)

if __name__ == "__main__":
    if not check_kernel_requirements():
      print("The kernel does not meet the necessary requirements, please check README.md")
      exit(1)

    parser = argparse.ArgumentParser(
        description="Example experiments for all io.knobs"
    )
    parser.add_argument(f"--cgroups", type=bool, required=False, default=False)
    parser.add_argument(f"--numdisks", type=int, required=False, default=0)
    for key in IO_KNOBS.keys():
        parser.add_argument(f"--{key}", type=bool, required=False, default=False)
    args = parser.parse_args()

    # Determine knobs to test
    knobs_to_test = []
    cgroups_active = False
    for arg, val in vars(args).items():
        if arg == "cgroups":
            cgroups_active = val 
        elif arg == "numdisks":
            NUMDISKS = [int(val)] if val else NUMDISKS
        elif val:
            knobs_to_test.append(IO_KNOBS[arg])

    if not len(knobs_to_test):
        knobs_to_test = list(IO_KNOBS.values())

    main(knobs_to_test, cgroups_active)
