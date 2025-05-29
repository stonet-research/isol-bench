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

@dataclass
class IOKnob:
    name: str
    configure_cgroups: Callable[[nvme.NVMeDevice, list[cgroups.Cgroup]], None]
    setup_fio_jobs: Callable[[list[cgroups.Cgroup]], fio.FioGlobalJob]

def iomax_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
    job_a = fio.FioSubJob('B')
    job_a.add_options([
      fio.DelayJobOption('0s'),
      fio.TimedOption('0s', '50s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.CgroupOption(f"{exp_cgroups[1].subpath}/fio-workload-b.service")
    ])

    job_b = fio.FioSubJob('A')
    job_b.add_options([
      fio.DelayJobOption('10s'),
      fio.TimedOption('0s', '70s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.CgroupOption(f"{exp_cgroups[0].subpath}/fio-workload-a.service")
    ])

    job_c = fio.FioSubJob('C')
    job_c.add_options([
      fio.DelayJobOption('20s'),
      fio.TimedOption('0s', '50s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.CgroupOption(f"{exp_cgroups[2].subpath}/fio-workload-c.service")
    ])

    return [job_a, job_b, job_c]

def ioprio_mq_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
    job_a = fio.FioSubJob('A')
    job_a.add_options([
      fio.DelayJobOption('0s'),
      fio.TimedOption('0s', '50s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.AllowedCPUsOption('2'),
      fio.CgroupOption(f"{exp_cgroups[1].subpath}/fio-workload-b.service")
    ])

    job_b = fio.FioSubJob('B')
    job_b.add_options([
      fio.DelayJobOption('10s'),
      fio.TimedOption('0s', '70s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.AllowedCPUsOption('2'),
      fio.CgroupOption(f"{exp_cgroups[0].subpath}/fio-workload-a.service")
    ])

    job_c = fio.FioSubJob('C')
    job_c.add_options([
      fio.DelayJobOption('20s'),
      fio.TimedOption('0s', '50s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.AllowedCPUsOption('2'),
      fio.CgroupOption(f"{exp_cgroups[2].subpath}/fio-workload-c.service")
    ]) 

    cgroup_a = cgroups.create_cgroup(f"example-workload-0.slice/fio-workload-a.service")
    cgroup_a.ioprio = exp_cgroups[0].ioprio
    cgroup_a.iocontrol_enabled = False
    cgroup_b = cgroups.create_cgroup(f"example-workload-1.slice/fio-workload-b.service")
    cgroup_b.ioprio = exp_cgroups[1].ioprio
    cgroup_b.iocontrol_enabled = False
    cgroup_c = cgroups.create_cgroup(f"example-workload-2.slice/fio-workload-c.service")
    cgroup_c.ioprio = exp_cgroups[2].ioprio
    cgroup_c.iocontrol_enabled = False

    return [job_a, job_b, job_c]

def ioprio_bfq_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
    job_a = fio.FioSubJob('A')
    job_a.add_options([
      fio.DelayJobOption('0s'),
      fio.TimedOption('0s', '50s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.AllowedCPUsOption('2'),
      fio.CgroupOption(f"{exp_cgroups[1].subpath}/fio-workload-b.service")
    ])

    job_b = fio.FioSubJob('B')
    job_b.add_options([
      fio.DelayJobOption('10s'),
      fio.TimedOption('0s', '70s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.AllowedCPUsOption('2'),
      fio.CgroupOption(f"{exp_cgroups[0].subpath}/fio-workload-a.service")
    ])

    job_c = fio.FioSubJob('C')
    job_c.add_options([
      fio.DelayJobOption('20s'),
      fio.TimedOption('0s', '50s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.AllowedCPUsOption('2'),
      fio.CgroupOption(f"{exp_cgroups[2].subpath}/fio-workload-c.service")
    ]) 

    cgroup_a = cgroups.create_cgroup(f"example-workload-0.slice/fio-workload-a.service")
    cgroup_a.ioprio = exp_cgroups[0].ioprio
    cgroup_a.iocontrol_enabled = False
    cgroup_b = cgroups.create_cgroup(f"example-workload-1.slice/fio-workload-b.service")
    cgroup_b.ioprio = exp_cgroups[1].ioprio
    cgroup_b.iocontrol_enabled = False
    cgroup_c = cgroups.create_cgroup(f"example-workload-2.slice/fio-workload-c.service")
    cgroup_c.ioprio = exp_cgroups[2].ioprio
    cgroup_c.iocontrol_enabled = False

    return [job_a, job_b, job_c]

def io_bfq_weight_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
    job_a = fio.FioSubJob('A')
    job_a.add_options([
      fio.DelayJobOption('0s'),
      fio.TimedOption('0s', '50s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.AllowedCPUsOption('2'),
      fio.CgroupOption(f"{exp_cgroups[1].subpath}/fio-workload-b.service")
    ])

    job_b = fio.FioSubJob('B')
    job_b.add_options([
      fio.DelayJobOption('10s'),
      fio.TimedOption('0s', '70s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.AllowedCPUsOption('2'),
      fio.CgroupOption(f"{exp_cgroups[0].subpath}/fio-workload-a.service")
    ])

    job_c = fio.FioSubJob('C')
    job_c.add_options([
      fio.DelayJobOption('20s'),
      fio.TimedOption('0s', '50s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.AllowedCPUsOption('2'),
      fio.CgroupOption(f"{exp_cgroups[2].subpath}/fio-workload-c.service")
    ]) 

    cgroup_a = cgroups.create_cgroup(f"example-workload-0.slice/fio-workload-a.service")
    cgroup_a.ioprio = exp_cgroups[0].ioprio
    cgroup_a.iocontrol_enabled = False
    cgroup_b = cgroups.create_cgroup(f"example-workload-1.slice/fio-workload-b.service")
    cgroup_b.ioprio = exp_cgroups[1].ioprio
    cgroup_b.iocontrol_enabled = False
    cgroup_c = cgroups.create_cgroup(f"example-workload-2.slice/fio-workload-c.service")
    cgroup_c.ioprio = exp_cgroups[2].ioprio
    cgroup_c.iocontrol_enabled = False

    return [job_a, job_b, job_c]

def io_latency_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
    job_a = fio.FioSubJob('A')
    job_a.add_options([
      fio.DelayJobOption('0s'),
      fio.TimedOption('0s', '50s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.AllowedCPUsOption('2'),
      fio.CgroupOption(f"{exp_cgroups[1].subpath}/fio-workload-b.service")
    ])

    job_b = fio.FioSubJob('B')
    job_b.add_options([
      fio.DelayJobOption('10s'),
      fio.TimedOption('0s', '70s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.AllowedCPUsOption('2'),
      fio.CgroupOption(f"{exp_cgroups[0].subpath}/fio-workload-a.service")
    ])

    job_c = fio.FioSubJob('C')
    job_c.add_options([
      fio.DelayJobOption('20s'),
      fio.TimedOption('0s', '50s'),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.AllowedCPUsOption('2'),
      fio.CgroupOption(f"{exp_cgroups[2].subpath}/fio-workload-c.service")
    ]) 

    return [job_a, job_b, job_c]


def global_setup_fio_job(device_name: str) -> fio.FioGlobalJob:
    job = fio.FioGlobalJob()
    job.add_options([
        fio.TargetOption(device_name),
        fio.JobOption(fio.JobWorkload.RAN_READ),
        fio.DirectOption(True),
        fio.GroupReportingOption(False),
        fio.ThreadOption(False), # < we need to set this because ioprio is not transferred on fork (shocking I know)
        fio.HighTailLatencyOption(),
        fio.SizeOption("100%"),
        fio.IOEngineOption(fio.IOEngine.IO_URING),
        fio.Io_uringFixedBufsOption(True),
        fio.Io_uringRegisterFilesOption(True)
    ])
    return job

def iomax_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    major_minor = nvme_device.major_minor
    
    cgroup_a = exp_cgroups[0]
    cgroup_b = exp_cgroups[1]
    cgroup_c = exp_cgroups[2]

    cgroup_a.iomax = cgroups.IOMax(major_minor, 1024 * 1024 * 500, None, None, None)
    cgroup_b.iomax = cgroups.IOMax(major_minor, 1024 * 1024 * 1500, None, None, None)
    cgroup_c.iomax = cgroups.IOMax(major_minor, 1024 * 1024 * 500, None, None, None)

def ioprio_mq_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    nvme_device.io_scheduler = nvme.IOScheduler.MQ_DEADLINE

    cgroup_a = exp_cgroups[0]
    cgroup_b = exp_cgroups[1]
    cgroup_c = exp_cgroups[2]

    cgroup_a.ioprio = cgroups.IOPriorityClass.IDLE
    cgroup_b.ioprio = cgroups.IOPriorityClass.PROMOTE_TO_RT
    cgroup_c.ioprio = cgroups.IOPriorityClass.RESTRICT_TO_BE

def ioprio_bfq_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    nvme_device.io_scheduler = nvme.IOScheduler.BFQ

    cgroup_a = exp_cgroups[0]
    cgroup_b = exp_cgroups[1]
    cgroup_c = exp_cgroups[2]

    cgroup_a.ioprio = cgroups.IOPriorityClass.IDLE
    cgroup_b.ioprio = cgroups.IOPriorityClass.PROMOTE_TO_RT
    cgroup_c.ioprio = cgroups.IOPriorityClass.RESTRICT_TO_BE

def io_bfq_weight_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    nvme_device.io_scheduler = nvme.IOScheduler.BFQ

    cgroup_a = exp_cgroups[0]
    cgroup_b = exp_cgroups[1]
    cgroup_c = exp_cgroups[2]

    cgroup_a.iobfqweight = cgroups.IOBFQWeight("default", 1)
    cgroup_b.iobfqweight = cgroups.IOBFQWeight("default", 1000)
    cgroup_c.iobfqweight = cgroups.IOBFQWeight("default", 100)


def io_latency_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    cgroup_a = exp_cgroups[0]
    cgroup_b = exp_cgroups[1]
    cgroup_c = exp_cgroups[2]

    cgroup_a.iolatency = cgroups.IOBFQWeight(nvme_device.major_minor, 1000)
    cgroup_b.iolatency = cgroups.IOBFQWeight(nvme_device.major_minor, 20)
    cgroup_c.iolatency = cgroups.IOBFQWeight(nvme_device.major_minor, 100)

def setup_cgroups() -> list[cgroups.Cgroup]:
    return [cgroups.create_cgroup(f"example-workload-{i}.slice") for i in range(0,5)]

def main(knobs_to_test: list[IOKnob]):
    nvme_device = get_nvmedev()
    outdir = f'./out/{nvme_device.eui}'
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

        for enabled in [True, False]:
            print(f"Configuring experiment [enabled={enabled}]")        
            cgroups.disable_iocontrol()
            del nvme_device.io_scheduler
            if enabled:
                knob.configure_cgroups(nvme_device, exp_cgroups)

            print(f"Generating experiment")        
            job = global_setup_fio_job(nvme_device.syspath)
            for ind, sjob in enumerate(knob.setup_fio_jobs(exp_cgroups)):
                sjob.add_options([fio.BWLogOption(f"./{outdir}/{knob.name}-{enabled}-{ind}")])
                job.add_job(sjob)
            job_gen.generate_job_file(f'./tmp/{knob.name}-{enabled}', job)

            print(f"Running experiment")        
            job_runner.run_job(f'./tmp/{knob.name}-{enabled}', f'./{outdir}/{knob.name}-{enabled}.json')

IO_KNOBS = {
    "iomax": IOKnob("io.max", iomax_configure_cgroups, iomax_setup_fio_jobs),
    "iopriomq": IOKnob("io.prio_class+mq", ioprio_mq_configure_cgroups, ioprio_mq_setup_fio_jobs),
    "iopriobfq": IOKnob("io.prio_class+bfq", ioprio_bfq_configure_cgroups, ioprio_bfq_setup_fio_jobs),
    "iobfqweight": IOKnob("io.bfq.weight", io_bfq_weight_configure_cgroups, io_bfq_weight_setup_fio_jobs),
    "iolatency": IOKnob("io.latency", io_latency_configure_cgroups, io_latency_setup_fio_jobs)
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Example experiments for all io.knobs"
    )
    for key in IO_KNOBS.keys():
        parser.add_argument(f"--{key}", type=bool, required=False, default=False)
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