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
NUMJOBS = [2, 4, 8, 16, 32, 64, 128, 256]

def proportional_slowdown(l: list[float], isol: list[float]):
    return [ll / lisol for ll, lisol in zip(l, isol)]

def jains_fairness_index(l: list[float], w: list[int]):
    if len(l) != len(w):
        raise ValueError("Incorrect args")
    n = len(l)
    lw = [ll / ww for ll, ww in zip(l,w)]
    f = (sum(lw) ** 2) / (n * sum([llw**2 for llw in lw]))
    return f

def proportional_slowdown_jains(l: list[float], w: list[int], isol: list[float]):
    pc = proportional_slowdown(l, isol)
    print(pc, isol, l, w)
    return jains_fairness_index(pc, w)

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

    # We want to use the default weight 100 if weights are uniform
    if sum(weights) == len(weights):
        for i, w in enumerate(weights): 
            exp_cgroups[i].ioweight = cgroups.IOBFQWeight("default", 100)
        return

    # Ensure weights scale up but we are using the full range (e.g., not below 100 if possible)
    for i, w in enumerate(weights): 
        exp_cgroups[i].iobfqweight = cgroups.IOBFQWeight("default", w) 

def mq_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], max_bw, weights):
    nvme_device.io_scheduler = nvme.IOScheduler.MQ_DEADLINE

    # Uniform
    if (sum(weights) == len(weights)):
        return 

    # I have no idea if this is a good idea, but lets do it
    w_threshold = sum(weights) / 3
    for i, w in enumerate(weights): 
        c = None
        if w < w_threshold:
            c = cgroups.IOPriorityClass.IDLE
        elif w < 2 * w_threshold:
            c = cgroups.IOPriorityClass.RESTRICT_TO_BE
        else:   
            c = cgroups.IOPriorityClass.PROMOTE_TO_RT
        exp_cgroups[i].ioprio = c

def iolat_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], max_bw, weights):
    major_minor = nvme_device.major_minor

    for index, group in enumerate(exp_cgroups):
        if index >= len(weights):
            break 
        tlat = 10 + weights[index]
        group.iolatency = cgroups.IOLatency(major_minor, tlat)

def iocost_configure_cgroups(nvme_device: nvme.NVMeDevice, exp_cgroups: list[cgroups.Cgroup], specified_bw, weights):
    model = cgroups.IOCostModel(nvme_device.major_minor, 'user', 'linear', 2706339840, 786432, 786432, 1063126016, 135560, 130734)
    qos = cgroups.IOCostQOS(nvme_device.major_minor, True,'user', 95.00, 1_000_000, 95.00, 1_000_000, 50.00, 150.00)
    cgroups.set_iocost(model, qos)

    # We want to use the default weight 100 if weights are uniform
    if sum(weights) == len(weights):
        for i, w in enumerate(weights): 
            exp_cgroups[i].ioweight = cgroups.IOWeight("default", 100)
        return

    # Ensure weights scale up but we are using the full range (e.g., not below 100 if possible)
    weight_jumper = 10_000 / (sum(weights))
    for i, w in enumerate(weights): 
        exp_cgroups[i].ioweight = cgroups.IOWeight("default", w) # round(w * weight_jumper))

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
        fio.QDOption(256),
        fio.RequestSizeOption(f"{4 * 1024}"),
        fio.ConcurrentWorkerOption(1),
        fio.TimedOption('20s', '60s'),
        fio.AllowedCPUsOption(CORES),
#        fio.Io_uringFixedBufsOption(True),
 #       fio.Io_uringRegisterFilesOption(False), 
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
        knob.configure_cgroups(nvme_device, exp_cgroups, (1024 * 1024 * 1024) * 10, [1])
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
            print(preamble, o)
            bw = float(o[0])
            jobs = int(o[1])
            saturation[filename] = bw
    return saturation


def unsaturated_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we go below saturation by dividing max by jobcount and creating a "ghost job"
    bw_rate = f"{ (saturation_point['min'] * 1024) // (numjobs+1)}"
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    sjob.add_options([
        roption
    ])
    return (sjob, bw_rate)

def unfair_unsaturated_job(sjob, saturation_point, numjobs, i, single_job_bw):
    div = [1, 2, 4, 8][i % 4]
    # Limit, we go below saturation by dividing max by jobcount and creating a "ghost job"
    bw_rate = f"{ ((saturation_point['min'] * 1024) // (numjobs+1)) / div}"
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    sjob.add_options([
        roption
    ])
    return (sjob, bw_rate)


def saturated_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    bw_rate = single_job_bw
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    sjob.add_options([
        roption
    ])
    return (sjob, bw_rate)

def unfairapp_saturated_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # We give some apps more than others
    div = [1, 2, 4, 8][i % 4]
    bw_rate = f"{int(single_job_bw // div)}"
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    sjob.add_options([
        roption
    ])
    return (sjob, bw_rate)

def requestsize_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    bw_rate = single_job_bw
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    soption = fio.RequestSizeOption(["4096", "65536"][i % 2])
    sjob.add_options([
        roption,
        soption
    ])
    return (sjob, bw_rate)

def requestsize_large_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    bw_rate = single_job_bw
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    soption = fio.RequestSizeOption(["4096", f"{1024 * 256}"][i % 2])
    sjob.add_options([
        roption,
        soption
    ])
    return (sjob, bw_rate)

def requestsize_split_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    bw_rate = single_job_bw
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    jstr = ""
    for j in range(2, 12):
        if len(jstr) > 1:
            jstr = jstr + ":"
        jstr = jstr + f"{2**j}k/10"
    soption = fio.BsSplitOption(jstr)
    sjob.add_options([
        roption,
        soption
    ])
    return (sjob, bw_rate)

def requestsize_range_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    bw_rate = single_job_bw
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    sizes = []
    for j in range(2, 12):
        sizes.append(f"{2**j}k")
    soption = fio.RequestSizeOption(sizes[i % (len(sizes))])
    sjob.add_options([
        roption,
        soption
    ])
    return (sjob, bw_rate)

def seqread_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    bw_rate = single_job_bw
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    joption = fio.JobOption(fio.JobWorkload.SEQ_READ)
    sjob.add_options([
        roption,
        joption
    ])
    return (sjob, bw_rate)

def mixedread_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    bw_rate = single_job_bw
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    joption = fio.JobOption([fio.JobWorkload.SEQ_READ, fio.JobWorkload.RAN_READ][i%2])
    sjob.add_options([
        roption,
        joption
    ])
    return (sjob, bw_rate)

def ranwrite_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    bw_rate = single_job_bw
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    joption = fio.JobOption(fio.JobWorkload.RAN_WRITE)
    toption = fio.TimedOption('20s', '10m')
    sjob.add_options([
        roption,
        joption,
        toption
    ])
    return (sjob, bw_rate)

def mixedwrite_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    bw_rate = single_job_bw
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    joption = fio.JobOption(fio.JobWorkload.MIXED)
    toption = fio.TimedOption('20s', '10m')
    sjob.add_options([
        roption,
        joption,
        toption
    ])
    return (sjob, bw_rate)

def mixedwrite2_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    bw_rate = single_job_bw
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    joption = fio.JobOption(fio.JobWorkload.MIXED)
    toption = fio.TimedOption('20s', '10m')
    moption = fio.RWMixRatioOption("90")
    sjob.add_options([
        roption,
        joption,
        toption,
        moption
    ])
    return (sjob, bw_rate)

def mixedranwrite3_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    bw_rate = single_job_bw
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    joption = fio.JobOption([fio.JobWorkload.RAN_WRITE, fio.JobWorkload.RAN_READ][i % 2])
    toption = fio.TimedOption('20s', '10m')
    sjob.add_options([
        roption,
        joption,
        toption
    ])
    return (sjob, bw_rate)

def mixedranwrite4_job(sjob, saturation_point, numjobs, i, single_job_bw):
    # Limit, we give each tenant as much as it can support
    bw_rate = single_job_bw
    roption = fio.RateOption(bw_rate, bw_rate, bw_rate)
    joption = fio.JobOption([fio.JobWorkload.RAN_WRITE, fio.JobWorkload.RAN_READ][i % 2])
    toption = fio.TimedOption('20s', '10m')
    coption = fio.ConcurrentWorkerOption('8')
    sjob.add_options([
        roption,
        joption,
        toption,
        coption
    ])
    return (sjob, bw_rate)




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

    with open(f'./out/{nvme_device.eui}/bfq.json', "r") as f:
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
    # General random read
    "unsaturated": Experiment("unsaturated", False, False, unsaturated_job),
    "unsaturatedw": Experiment("unsaturatedw", False, True, unsaturated_job),
    "unfairunsaturated": Experiment("unsaturated", False, False, unfair_unsaturated_job),
    "saturated": Experiment("saturated", True, False, saturated_job),
    "saturatedw": Experiment("saturatedw", True, True, saturated_job),
    "saturatedunfair": Experiment("saturatedunfairw", True, False, unfairapp_saturated_job),
    "saturatedunfairw": Experiment("saturatedunfairw", True, True, unfairapp_saturated_job),
    # Random read rq size impact
    "requestsize": Experiment("requestsize", True, False, requestsize_job),
    "requestsizew": Experiment("requestsizew", True, True, requestsize_job),
    "requestsizelarge": Experiment("requestsizelarge", True, False, requestsize_large_job),
    "requestsizesplit": Experiment("requestsizesplit", True, False, requestsize_split_job),
    "requestsizerange": Experiment("requestsizerange", True, False, requestsize_range_job),
    # Read access pattern
    "seqread": Experiment("seqread", True, False, seqread_job),
    "mixedread": Experiment("mixedread", True, False, mixedread_job),
    # Write-only
    "ranwrite": Experiment("ranwrite", True, False, ranwrite_job),
    "ranwritew": Experiment("ranwritew", True, True, ranwrite_job),
   # R/W-mix
    "mixedwrite": Experiment("mixedwrite", True, False, mixedwrite_job),
    "mixedwritew": Experiment("mixedwritew", True, True, mixedwrite_job),
    "mixed90write": Experiment("mixed90write", True, False, mixedwrite2_job),
    "mixed90writew": Experiment("mixed90writew", True, True, mixedwrite2_job),
    "mixedwrite3": Experiment("mixedwrite3", True, False, mixedranwrite3_job),
    "mixedwrite3w": Experiment("mixedwrite3w", True, True, mixedranwrite3_job),
    "mixedwrite4": Experiment("mixedwrite4", True, False, mixedranwrite4_job),
    "mixedwrite4w": Experiment("mixedwrite4w", True, True, mixedranwrite4_job),
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
        min_num_jobs = ((saturation_point['max'] / 1024) / (single_job_bw / (1024 * 1024))) + 1
        print(f"T-app in isolation gets {single_job_bw / (1024 * 1024)} MiB/s with {knob.name} [sat is {saturation_point['max'] / 1024}]; so we need at least {min_num_jobs} jobs for saturation")

        # We do in reverse so we can kill "early"
        njs = [256] if "write" in experiment.name else NUMJOBS[::-1]
        for numjobs in njs:
            if numjobs < min_num_jobs and not "unsaturated" in experiment.name:
                print(f"Ignoring numjobs={numjobs} as it does not saturate")
                continue
            elif numjobs >= min_num_jobs and "unsaturated" in experiment.name:
                print(f"Ignoring numjobs={numjobs} as it saturates")
                continue
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
            rates = []
            for i, tapp in enumerate(setup_sjobs(exp_cgroups, numjobs)):
                tapp, bw_rate = experiment.change_jobs(tapp, saturation_point, numjobs, i, single_job_bw)              
                rates.append(float(bw_rate) / 1024)
                gjob.add_job(tapp) 
                # .
                sjob_cgroup_path = f"{exp_cgroups[i].subpath}/fio-workload.service"
                cgroups.create_cgroup_service(sjob_cgroup_path)
            job_gen.generate_job_file(f'./tmp/{experiment.name}-{knob.name}-{numjobs}', gjob)

            print(f"Running experiment [experiment={experiment.name} numjobs={numjobs}]")                    

            fioproc = job_runner.run_job_deferred(\
                f'./tmp/{experiment.name}-{knob.name}-{numjobs}',\
                f'./{outdir}/{experiment.name}-{knob.name}-{numjobs}.json')
            fioproc.wait()

            with open(f'./{outdir}/{experiment.name}-{knob.name}-{numjobs}.json', 'r') as f:
                js = json.load(f)
                vs = [float(j['read']['bw_mean']) + float(j['write']['bw_mean'])for j in js['jobs']]
                jains = proportional_slowdown_jains(vs, weights, rates)
                jains2 = jains_fairness_index(vs, weights)
                bwsum = sum(vs) / (1024 * 1024)
                print(f"Jains fairness: {jains} or {jains2} -- BW sum {bwsum} GiB/s")

            # Cleanup state
            if not nvme_device.isoptane and "write" in experiment.name:
                print("Resetting device state by preconditioning")
                nvme_format(nvme_device)
                fioproc = job_runner.run_job_deferred(\
                    f'./precondition.fio',\
                    f'./{outdir}/{experiment.name}-precond.json',
                    fio_extra_opts=[f"filename={nvme_device.syspath}"])
                fioproc.wait()
                print("Done preconditioning")

def run_experiments(experiments_to_run: list[Experiment], knobs_to_test: list[IOKnob]):
    nvme_device = get_nvmedev()
    outdir = f'./out/{nvme_device.eui}'
    os.makedirs(outdir, exist_ok = True)
    os.makedirs(f'./tmp', exist_ok = True)

    exp_cgroups = setup_cgroups()
    saturation_point = parse_saturation_points(nvme_device)
    print(saturation_point)

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
