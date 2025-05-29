import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'util')))

from dataclasses import dataclass
from typing import Callable
import argparse

import fio
from util_sysfs import cgroups as cgroups
from util_sysfs import nvme as nvme

@dataclass
class IOKnob:
    name: str
    configure_cgroups: Callable[[str, list[cgroups.Cgroup]], None]
    setup_fio_jobs: Callable[[list[cgroups.Cgroup]], fio.FioGlobalJob]

def iomax_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
    job_a = fio.FioSubJob('A')
    job_a.add_options([
      fio.TimedOption('0s', '1m'),
      fio.RateOption('500m', '', ''),
      fio.QDOption(256),
      fio.CgroupOption(exp_cgroups[0].subpath)
    ])


    job_b = fio.FioSubJob('A')
    job_b.add_options([
      fio.TimedOption('0s', '20s'),
      fio.RateOption('500m', '', ''),
      fio.QDOption(256),
      fio.CgroupOption(exp_cgroups[0].subpath)
    ])


    return [job_a]

def global_setup_fio_job(device_name: str) -> fio.FioGlobalJob:
    job = fio.FioGlobalJob()
    job.add_options([
        fio.TargetOption(device_name),
        fio.JobOption(fio.JobWorkload.RAN_READ),
        fio.DirectOption(True),
        fio.GroupReportingOption(False),
        fio.ThreadOption(False),
        fio.HighTailLatencyOption(),
        fio.SizeOption("100%"),
        fio.IOEngineOption(fio.IOEngine.IO_URING),
        fio.Io_uringFixedBufsOption(True),
        fio.Io_uringRegisterFilesOption(True)
    ])
    return job

def iomax_configure_cgroups(major_minor: str, exp_cgroups: list[cgroups.Cgroup]):
    cgroup_a = exp_cgroups[0]
    cgroup_b = exp_cgroups[1]

    cgroup_a.iomax = cgroups.IOMax(major_minor, 1024 * 1024 * 250, None, None, None)
    cgroup_a.iomax = cgroups.IOMax(major_minor, 10, None, None, None)
    cgroup_b.iomax = cgroups.IOMax(major_minor, 1024 * 1024 * 250, None, None, None)

def setup_cgroups() -> list[cgroups.Cgroup]:
    return [cgroups.create_cgroup(f"example-workload-{i}.slice") for i in range(0,5)]

def get_nvmedev() -> nvme.NVMeDevice:
    nvme_path=os.path.abspath(os.path.join(os.path.dirname(__file__), 'tmp', 'testdrive'))
    if not os.path.exists(nvme_path):
        raise ValueError("No nvme drive speciifed, please check the README.md")
    with open(nvme_path, "r") as f:
        return nvme.find_nvme_with_eui(f.readline().strip())

def main(knobs_to_test: list[IOKnob]):
    nvme_device = get_nvmedev()
    exp_cgroups = setup_cgroups()
    job_gen = fio.FioJobGenerator(True)
    job_runner = fio.FioRunner('sudo ../dependencies/fio/fio', fio.FioRunnerOptions(overwrite=True, parse_only=False))

    for knob in knobs_to_test: 
        print(f"___________________________________")
        print(f"Experiment [{knob.name}]") 
        print(f"___________________________________")
        
        print(f"Configuring experiment")        
        cgroups.disable_iocontrol()
        del nvme_device.io_scheduler
        knob.configure_cgroups(nvme_device.major_minor, exp_cgroups)

        print(f"Generating experiment")        
        job = global_setup_fio_job(nvme_device.syspath)
        for sjob in knob.setup_fio_jobs(exp_cgroups):
            job.add_job(sjob)
        job_gen.generate_job_file(f'./tmp/{knob.name}', job)

        print(f"Running experiment")        
        job_runner.run_job(f'./tmp/{knob.name}', f'./out/{knob.name}.json')

IO_KNOBS = {
    "iomax": IOKnob("io.max", iomax_configure_cgroups, iomax_setup_fio_jobs)
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Example experiments for all io.knobs"
    )
    parser.add_argument("--iomax", type=bool, required=False, default=False)
    args = parser.parse_args()

    # Determine knobs to test
    knobs_to_test = []
    for arg, val in vars(args).items():
        if arg not in IO_KNOBS:
            raise ValueError(f"Knob {arg} not known")
        elif val:
            knobs_to_test.append(IO_KNOBS[arg])

    if not len(knobs_to_test):
        knobs_to_test = list(IO_KNOBS.values())
    
    main(knobs_to_test)