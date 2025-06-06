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
NUMJOBS = [4, 8, 16, 32, 64, 128]

@dataclass
class IOKnob:
    name: str
    configure_cgroups: Callable[[nvme.NVMeDevice, list[cgroups.Cgroup]], None]

@dataclass
class Experiment:
    name: str
    saturated: bool
    weighted: bool
    change_jobs: bool

def none_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], max_bw, weights):
    pass

def iomax_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], max_bw, weights):
    total_weight = sum(weights) 

    major_minor = nvme_device.major_minor
    for index, group in enumerate(exp_cgroups):
        if index >= len(weights):
            break
        weight = weights[index] / total_weight
        group.iomax = cgroups.IOMax(major_minor, int(weight * max_bw), int(weight * max_bw), 10_000_000, 10_000_000)

def bfq_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], max_bw, weights):
    nvme_device.io_scheduler = nvme.IOScheduler.BFQ

def mq_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], max_bw, weights):
    nvme_device.io_scheduler = nvme.IOScheduler.MQ_DEADLINE

def iolat_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], max_bw, weights):
    major_minor = nvme_device.major_minor
    for group in exp_cgroups:
        group.iolatency = cgroups.IOLatency(major_minor, 10)

def iocost_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], specified_bw, weights):
    model = cgroups.IOCostModel(nvme_device.major_minor, 'user', 'linear', 2706339840, 89698, 110036, 1063126016, 135560, 130734)
    qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 95.00, 100, 95.00, 1000, 50.00, 150.00)
    cgroups.set_iocost(model, qos)

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
        fio.IOEngineOption(fio.IOEngine.IO_URING),
        fio.Io_uringFixedBufsOption(True),
        fio.Io_uringRegisterFilesOption(True),
        fio.QDOption(256),
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

def find_saturation_point(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], knob: IOKnob, out:str):
    job_gen = fio.FioJobGenerator(True)
    job_runner = fio.FioRunner('sudo ../dependencies/fio/fio', fio.FioRunnerOptions(overwrite=True, parse_only=False))

    js = [1, 2, 4, 16, 32]
    for numjobs in js:
        file_preamble = f'saturation-{knob.name}-{numjobs}'
        # Configure
        cgroups.disable_iocontrol_with_groups(exp_cgroups)
        del nvme_device.io_scheduler
        knob.configure_cgroups(nvme_device, exp_cgroups)
        for group in exp_cgroups:
            group.force_cpuset_cpus(CORES)

        # Setup job
        gjob = setup_gjob(nvme_device.syspath)
        gjob.add_options([
            fio.GroupReportingOption(True),
        ])
        for tapp in setup_sjobs(exp_cgroups, numjobs):
            gjob.add_job(tapp)
        job_gen.generate_job_file(f'./tmp/{file_preamble}', gjob)
        
        # Run
        fioproc = job_runner.run_job_deferred(f'./tmp/{file_preamble}', f'./out/{nvme_device.eui}/{file_preamble}.json')
        fioproc.wait()

        # Disable
        cgroups.disable_iocontrol_with_groups(exp_cgroups)
        del nvme_device.io_scheduler
        for group in exp_cgroups:
            group.force_cpuset_cpus('')
    
    # Analyze
    maxbw  = 0
    maxbwj = 0
    for numjobs in js:
        with open(f'./out/{nvme_device.eui}/saturation-{knob.name}-{numjobs}.json') as f:
            j = json.load(f)
            bw = j['jobs'][0]['read']['bw_mean']
            if bw > maxbw:
                maxbw = bw
                maxbwj = numjobs
    with open(f'{out}', 'w') as f:
        f.write(f'{maxbw}@{maxbwj}')

def find_saturation_points(mink: IOKnob, maxk: IOKnob):
    nvme_device = get_nvmedev()
    exp_cgroups = setup_cgroups()

    for knob, out in [(mink, 'min'), (maxk, 'max')]:
        find_saturation_point(nvme_device, exp_cgroups, knob, f'./out/{nvme_device.eui}/saturation-{out}')

def parse_saturation_points(nvme_device: nvme.NVMeDevice):
    preamble = f'./out/{nvme_device.eui}/saturation' 

    saturation = {}
    for filename in ["min", "max"]:
        with open(f"{preamble}-{filename}", "r") as f:
            o = f.readline().strip().split('@')
            bw = float(o[0])
            jobs = int(o[1])
            saturation[filename] = bw
    return saturation


def unsaturated_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we go below saturation by dividing max by jobcount and creating a "ghost job"
    bw = f"{ (saturation_point['min'] * 1024) // (numjobs+1)}"
    roption = fio.RateOption(bw, bw, bw)
    sjob.add_options([
        roption
    ])
    return sjob

def saturated_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    roption = fio.RateOption(single_job_bw, single_job_bw, single_job_bw)
    sjob.add_options([
        roption
    ])
    return sjob

def unfairapp_saturated_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # We give some apps more than others
    div = (i % 4) + 1
    #
    bw = f"{int(single_job_bw // div)}"
    roption = fio.RateOption(bw, bw, bw)
    sjob.add_options([
        roption
    ])
    return sjob

def requestsize_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    roption = fio.RateOption(single_job_bw, single_job_bw, single_job_bw)
    soption = fio.RequestSizeOption(["4096", "65536"][i % 2])
    sjob.add_options([
        roption,
        soption
    ])
    return sjob

def generate_singleknob_bw(name, filename, nvme_device, exp_cgroups):
    job_gen = fio.FioJobGenerator(True)
    job_runner = fio.FioRunner('sudo ../dependencies/fio/fio', fio.FioRunnerOptions(overwrite=True, parse_only=False))

    # Setup job
    gjob = setup_gjob(nvme_device.syspath)
    gjob.add_options([
        fio.GroupReportingOption(True),
    ])
    gjob.add_job(setup_sjobs(exp_cgroups, 1)[0])
    job_gen.generate_job_file(f'./tmp/{name}', gjob)
        
    # Run
    fioproc = job_runner.run_job_deferred(f'./tmp/{name}', filename)
    fioproc.wait()   

    # Setup job large rq
    gjob = setup_gjob(nvme_device.syspath)
    gjob.add_options([
        fio.GroupReportingOption(True),
        fio.RequestSizeOption("65536")
    ])
    gjob.add_job(setup_sjobs(exp_cgroups, 1)[0])
    job_gen.generate_job_file(f'./tmp/{name}-rq', gjob)
        
    # Run
    fioproc = job_runner.run_job_deferred(f'./tmp/{name}-rq', f"{filename}-rq")
    fioproc.wait()   

def get_singleknob_bw(knob : IOKnob, nvme_device, exp_cgroups):
    filename = f'./out/{nvme_device.eui}/{knob.name}.json' 

    if not os.path.exists(filename):
        print("Determining T-app performance")
        generate_singleknob_bw(knob.name, filename, nvme_device, exp_cgroups)

    with open(filename, "r") as f:
        j = json.load(f)
        return int(j['jobs'][0]['read']['bw_mean']) * 1024

IO_KNOBS = {
    "none": IOKnob("none", none_configure_cgroups),
    "bfq": IOKnob("bfq", bfq_configure_cgroups),
    "mq": IOKnob("mq", mq_configure_cgroups),
    "iomax": IOKnob("iomax", iomax_configure_cgroups),
    "iolat": IOKnob("iolat", iolat_configure_cgroups),
    "iocost": IOKnob("iocost", iocost_configure_cgroups),
}

EXPERIMENTS = {
    "unsaturated": Experiment("unsaturated", False, False, unsaturated_job),
    "saturated": Experiment("saturated", True, False, saturated_job),
    "unfairapp": Experiment("unfairapp", True, False, unfairapp_saturated_job),
    "requestsize": Experiment("requestsize", True, False, requestsize_job),
}


def run_experiment(experiment: Experiment, knobs_to_test: list[IOKnob], nvme_device: nvme.NVMeDevice, exp_cgroups, saturation_point):
    job_gen = fio.FioJobGenerator(True)
    job_runner = fio.FioRunner('sudo ../dependencies/fio/fio', fio.FioRunnerOptions(overwrite=True, parse_only=False))
    outdir = f'./out/{nvme_device.eui}'


    for knob in knobs_to_test: 

        print(f"___________________________________")
        print(f"Experiment [{knob.name}]") 
        print(f"___________________________________")

        print(f"Configuring experiment [{experiment.name}]")        
        cgroups.disable_iocontrol_with_groups(exp_cgroups)
        del nvme_device.io_scheduler
        
        knob.configure_cgroups(nvme_device, exp_cgroups, (1024 * 1024 * 1024 * 10), [1])

        for group in exp_cgroups:
            group.force_cpuset_cpus(CORES)

        single_job_bw = get_singleknob_bw(knob, nvme_device, exp_cgroups)
        print(f"T-app in isolation gets {single_job_bw / (1024 * 1024)} MiB/s with {knob.name} [sat is {saturation_point['max'] / 1024}]")

        # We do in reverse so we can kill "early"
        for numjobs in NUMJOBS[::1]:
            print(f"Generating experiment [numjobs={numjobs}]")        

            weights = []
            if experiment.weighted:
                weights = list(range(1, numjobs+1)) 
            else:
                weights = [1 for _ in range(numjobs)]
            knob.configure_cgroups(nvme_device, exp_cgroups, saturation_point['max'] * 1024, weights)

            gjob = setup_gjob(nvme_device.syspath)
            gjob.add_options([
                fio.GroupReportingOption(False),
            ])
            for i, tapp in enumerate(setup_sjobs(exp_cgroups, numjobs)):
                tapp = experiment.change_jobs(tapp, saturation_point, numjobs, i, single_job_bw)              
                gjob.add_job(tapp)      
            job_gen.generate_job_file(f'./tmp/{experiment.name}-{knob.name}-{numjobs}', gjob)

            print(f"Running experiment [experiment={experiment.name} numjobs={numjobs}]")                    

            fioproc = job_runner.run_job_deferred(\
                f'./tmp/{experiment.name}-{knob.name}-{numjobs}',\
                f'./{outdir}/{experiment.name}-{knob.name}-{numjobs}.json')
            fioproc.wait()

def run_experiments(experiments_to_run: list[Experiment], knobs_to_test: list[IOKnob]):
    nvme_device = get_nvmedev()
    outdir = f'./out/{nvme_device.eui}'
    os.makedirs(outdir, exist_ok = True)
    os.makedirs(f'./tmp', exist_ok = True)

    exp_cgroups = setup_cgroups()
    saturation_point = parse_saturation_points(nvme_device)

    # Run
    for experiment in experiments_to_run:
        run_experiment(experiment, knobs_to_test, nvme_device, exp_cgroups, saturation_point)
   
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
    parser.add_argument(f"--find_saturation", type=bool, required=False, default=False)
    parser.add_argument(f"--min_saturation", type=str, required=False, default=False)
    parser.add_argument(f"--max_saturation", type=str, required=False, default=False)
    # cgroups
    for key in IO_KNOBS.keys():
        parser.add_argument(f"--{key}", type=bool, required=False, default=False)
    for key in EXPERIMENTS.keys():
        parser.add_argument(f"--{key}", type=bool, required=False, default=False)
    args = parser.parse_args()

    # Determine knobs to test
    knobs_to_test = []
    experiments_to_run = []
    find_saturation = False
    min_saturation = max_saturation = None
    for arg, val in vars(args).items():
        if arg == "find_saturation":
            find_saturation = val
        elif arg == "min_saturation":
            min_saturation = IO_KNOBS[val] if val in IO_KNOBS else None
        elif arg == "max_saturation":
            max_saturation = IO_KNOBS[val] if val in IO_KNOBS else None
        elif arg in IO_KNOBS and val:
            knobs_to_test.append(IO_KNOBS[arg])
        elif arg in EXPERIMENTS and val:
            experiments_to_run.append(EXPERIMENTS[arg])
    
    # Find saturation
    if find_saturation:
        if min_saturation == None or max_saturation == None:
            raise ValueError("Incorrect setup, set min and max for saturation point")
        find_saturation_points(min_saturation, max_saturation)
    # Normal experiment
    else:
        if not len(experiments_to_run):
            experiments_to_run = list(EXPERIMENTS.values())
        if not len(knobs_to_test):
            knobs_to_test = list(IO_KNOBS.values())
        run_experiments(experiments_to_run, knobs_to_test)
