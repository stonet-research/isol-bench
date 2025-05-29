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
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.CgroupOption(f"{exp_cgroups[0].subpath}/fio-workload-a.service")
    ])

    job_b = fio.FioSubJob('B')
    job_b.add_options([
      fio.TimedOption('0s', '20s'),
      fio.DelayJobOption('20s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.CgroupOption(f"{exp_cgroups[1].subpath}/fio-workload-b.service")
    ])

    return [job_a, job_b]

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

def setup_cgroups() -> list[cgroups.Cgroup]:
    return [cgroups.create_cgroup(f"example-workload-{i}.slice") for i in range(0,5)]

def get_nvmedev() -> nvme.NVMeDevice:
    nvme_path=os.path.abspath(os.path.join(os.path.dirname(__file__), 'tmp', 'testdrive'))
    if not os.path.exists(nvme_path):
        raise ValueError("No nvme drive specified, please check the README.md")
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

        for enabled in [True, False]:
            print(f"Configuring experiment [enabled={enabled}]")        
            cgroups.disable_iocontrol()
            del nvme_device.io_scheduler
            if enabled:
                knob.configure_cgroups(nvme_device.major_minor, exp_cgroups)

            print(f"Generating experiment")        
            job = global_setup_fio_job(nvme_device.syspath)
            for ind, sjob in enumerate(knob.setup_fio_jobs(exp_cgroups)):
                sjob.add_options([fio.BWLogOption(f"./out/{knob.name}-{enabled}-{ind}")])
                job.add_job(sjob)
            job_gen.generate_job_file(f'./tmp/{knob.name}-{enabled}', job)

            print(f"Running experiment")        
            job_runner.run_job(f'./tmp/{knob.name}-{enabled}', f'./out/{knob.name}-{enabled}.json')

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