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
EXPERIMENT_MAX_TENANT_COUNT=5

@dataclass
class IOKnob:
    name: str
    configure_cgroups: Callable[[nvme.NVMeDevice, list[cgroups.Cgroup]], None]
    setup_fio_jobs: Callable[[list[cgroups.Cgroup]], fio.FioGlobalJob]

def example_job_setup(exp_cgroups: list[cgroups.Cgroup]):
  sjobs = []
  for sjob in [
    (1, 'b', '0s', '50s'),
    (0, 'a', '10s', '70s'),
    (2, 'c', '20s', '50s')
  ]:
    index  = sjob[0]
    sjob_name   = sjob[1]
    sjob_start  = sjob[2]
    sjob_runtime = sjob[3]
    sjob_cgroup_path = f"{exp_cgroups[index].subpath}/fio-workload-{sjob_name}.service"
    
    sjob = fio.FioSubJob(sjob_name)
    sjob.add_options([
      fio.DelayJobOption(sjob_start),
      fio.TimedOption('0s', sjob_runtime),
      fio.RateOption('1500m', '', ''),
      fio.QDOption(8),
      fio.RequestSizeOption(f"{64 * 1024}"),
      fio.ConcurrentWorkerOption(1),
      fio.CgroupOption(sjob_cgroup_path),
      fio.AllowedCPUsOption(f'{2+index}'),
    ])
    sjobs.append(sjob)
  
    # We need to create service group as well. 
    cgroups.create_cgroup_service(sjob_cgroup_path)
       
  return sjobs

def none_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
  return example_job_setup(exp_cgroups)

def iomax_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
  return example_job_setup(exp_cgroups)

def mq_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
  return example_job_setup(exp_cgroups)

def bfq_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
  return example_job_setup(exp_cgroups)

def ioprio_mq_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
  return example_job_setup(exp_cgroups)

def ioprio_bfq_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
  return example_job_setup(exp_cgroups)

def ioprio_kyber_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
  return example_job_setup(exp_cgroups)

def io_bfq_weight_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
  return example_job_setup(exp_cgroups)

def io_latency_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
  return example_job_setup(exp_cgroups)

def io_cost_setup_fio_jobs(exp_cgroups: list[cgroups.Cgroup]):
  return example_job_setup(exp_cgroups)

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

def none_configure_cgroups(a, b):
    pass

def iomax_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    major_minor = nvme_device.major_minor
    
    cgroup_a = exp_cgroups[0]
    cgroup_b = exp_cgroups[1]
    cgroup_c = exp_cgroups[2]

    cgroup_a.iomax = cgroups.IOMax(major_minor, 1024 * 1024 * 500, None, None, None)
    cgroup_b.iomax = cgroups.IOMax(major_minor, 1024 * 1024 * 1500, None, None, None)
    cgroup_c.iomax = cgroups.IOMax(major_minor, 1024 * 1024 * 500, None, None, None)

def mq_configure_cgroups(nvme_device: nvme.NVMeDevice, *_):
    nvme_device.io_scheduler = nvme.IOScheduler.MQ_DEADLINE

def bfq_configure_cgroups(nvme_device: nvme.NVMeDevice, *_):
    nvme_device.io_scheduler = nvme.IOScheduler.BFQ

def ioprio_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    cgroup_a = exp_cgroups[0]
    cgroup_b = exp_cgroups[1]
    cgroup_c = exp_cgroups[2]

    cgroup_a.ioprio = cgroups.IOPriorityClass.IDLE
    cgroup_b.ioprio = cgroups.IOPriorityClass.PROMOTE_TO_RT
    cgroup_c.ioprio = cgroups.IOPriorityClass.RESTRICT_TO_BE

def ioprio_mq_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    mq_configure_cgroups(nvme_device, exp_cgroups)
    ioprio_configure_cgroups(nvme_device, exp_cgroups)

def ioprio_bfq_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    bfq_configure_cgroups(nvme_device, exp_cgroups)
    ioprio_configure_cgroups(nvme_device, exp_cgroups)

def ioprio_kyber_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    nvme_device.io_scheduler = nvme.IOScheduler.KYBER
    ioprio_configure_cgroups(nvme_device, exp_cgroups)

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

    cgroup_a.iolatency = cgroups.IOLatency(nvme_device.major_minor, 1000)
    cgroup_b.iolatency = cgroups.IOLatency(nvme_device.major_minor, 20)
    cgroup_c.iolatency = cgroups.IOLatency(nvme_device.major_minor, 100)

def io_cost_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    model = cgroups.get_iocostmodel_from_nvme_model(nvme_device)
    qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 95.00, 100, 95.00, 1000, 50.00, 150.00)
    cgroups.set_iocost(model, qos)

    cgroup_a = exp_cgroups[0]
    cgroup_b = exp_cgroups[1]
    cgroup_c = exp_cgroups[2]

    cgroup_a.ioweight = cgroups.IOWeight("default", 100)
    cgroup_b.ioweight = cgroups.IOWeight("default", 100)
    cgroup_c.ioweight = cgroups.IOWeight("default", 100)

def io_costw_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup]):
    io_cost_configure_cgroups(nvme_device, exp_cgroups)

    cgroup_a = exp_cgroups[0]
    cgroup_b = exp_cgroups[1]
    cgroup_c = exp_cgroups[2]

    cgroup_a.ioweight = cgroups.IOWeight("default", 1)
    cgroup_b.ioweight = cgroups.IOWeight("default", 1000)
    cgroup_c.ioweight = cgroups.IOWeight("default", 100)

def setup_cgroups() -> list[cgroups.Cgroup]:
    return [cgroups.create_cgroup(f"{EXPERIMENT_CGROUP_PATH_PREAMBLE}-{i}.slice") for i in range(0,EXPERIMENT_MAX_TENANT_COUNT)]

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

    original_nvme_scheduler = nvme_device.io_scheduler
    for knob in knobs_to_test: 
        print(f"___________________________________")
        print(f"Experiment [{knob.name}]") 
        print(f"___________________________________")

        print(f"Configuring experiment")        
        cgroups.disable_iocontrol_with_groups(exp_cgroups)
        del nvme_device.io_scheduler
        knob.configure_cgroups(nvme_device, exp_cgroups)

        print(f"Generating experiment")        
        job = global_setup_fio_job(nvme_device.syspath)
        for ind, sjob in enumerate(knob.setup_fio_jobs(exp_cgroups)):
            sjob.add_options([fio.BWLogOption(f"./{outdir}/{knob.name}-{ind}")])
            job.add_job(sjob)
        job_gen.generate_job_file(f'./tmp/{knob.name}', job)

        print(f"Running experiment")        
        job_runner.run_job(f'./tmp/{knob.name}', f'./{outdir}/{knob.name}.json')
    cgroups.disable_iocontrol_with_groups(exp_cgroups)
    nvme_device.io_scheduler = original_nvme_scheduler

IO_KNOBS = {
    "none": IOKnob("none", none_configure_cgroups, none_setup_fio_jobs),
    "mq": IOKnob("mq", mq_configure_cgroups, mq_setup_fio_jobs),
    "bfq": IOKnob("bfq", bfq_configure_cgroups, bfq_setup_fio_jobs),
    "iomax": IOKnob("io.max", iomax_configure_cgroups, iomax_setup_fio_jobs),
    "iopriomq": IOKnob("io.prio_class+mq", ioprio_mq_configure_cgroups, ioprio_mq_setup_fio_jobs),
    "iopriobfq": IOKnob("io.prio_class+bfq", ioprio_bfq_configure_cgroups, ioprio_bfq_setup_fio_jobs),
    "iopriokyber": IOKnob("io.prio_class+kyber", ioprio_kyber_configure_cgroups, ioprio_kyber_setup_fio_jobs),
    "iobfqweight": IOKnob("io.bfq.weight", io_bfq_weight_configure_cgroups, io_bfq_weight_setup_fio_jobs),
    "iolatency": IOKnob("io.latency", io_latency_configure_cgroups, io_latency_setup_fio_jobs),
    "iocost": IOKnob("io.cost", io_cost_configure_cgroups, io_cost_setup_fio_jobs),
    "iocostw": IOKnob("io.cost+weights", io_costw_configure_cgroups, io_cost_setup_fio_jobs)
}

if __name__ == "__main__":
    if not check_kernel_requirements():
      print("The kernel does not meet the necessary requirements, please check README.md")
      exit(1)

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
