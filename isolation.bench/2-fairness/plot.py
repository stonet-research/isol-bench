import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'util')))

import csv
import json
import datetime as dt
import os.path
import argparse
import statistics

from util_sysfs.bench import *
from util_sysfs.perf import get_perf_cycles
from plot_utils import *
import matplotlib.pyplot as plt

KNOBS = ["none", "iomax", "iolat", "iocost", "mq", "bfq2"]
LABELS = ["none", "io.max", "io.latency", "io.cost", "MQ-DL", "BFQ"]
WORKLOADS = {
    'randread' : '',
    '64k' : '-rq',
    '256k': '-rqextra',
    'seqread': '-seqr',
    'randwrite': '-ranw',
    'mixed': '-mixed',
    'mixed90': '-mixed90'
}

nvme_device = get_nvmedev()
set_standard_font()

def avg(y):
    return sum(y) / len(y) if len(y) else 0

def parse_fio(filename):
    with open(filename, 'r') as f:
        js = json.load(f)
        return js 

def get_isol():
    o = {}
    filepath_preamble = f"./out/{nvme_device.eui}"
    for knob in KNOBS:
        o[knob] = {}   
        for workload in WORKLOADS.keys():
            try:
                js = parse_fio(f"{filepath_preamble}/{knob}.json{WORKLOADS[workload]}")
                v = (js['jobs'][0]['read']['bw_mean'] * 1024) + (js['jobs'][0]['write']['bw_mean'] * 1024)
                o[knob][workload] = v
            except:
                print(f"Workload {workload} is not defined for {knob}")
    return o

isol = get_isol()

yo = []
yoe = []

for experiment, weighted in [
        ("unsaturated", False),  
        ("unsaturatedw", True),  
        ("saturated", False),  
        ("saturatedw", True), 
        ("requestsize", False),
        ("requestsizew", True),
        ("requestsizelarge", False),
        ("seqread", False),
        ("mixedread", False),
        ("ranwrite", False),
        ("mixedwrite", False),
        ("mixed90write", False),
        ("mixedwrite3", False),
        ("requestsizerange", False),
    ]:
    print(f"EXPERIMENT {experiment}")
    print('----------------------------------------------------------')
    numjobss = [16, 32, 64, 128, 256] if not "write" in experiment else [256]
    if "unsaturated" in experiment:
        numjobss = [2, 4]
    for numjobs in numjobss:
        print(numjobs)
        y = []
        ye = []
        yp = []
        ype = []
        for knob in KNOBS:
            suby = []
            subyp = []
            for it in list(range(10)):
                filename = f'./out/{nvme_device.eui}/{experiment}-{knob}-{numjobs}-{it}.json'
                try:
                    js = parse_fio(filename)
                
                    vs = [float(j['read']['bw_mean']) + float(j['write']['bw_mean'])for j in js['jobs']]
                    weights =  list(range(1, len(vs) +1)) if weighted else len(vs) * [1] 
                    rates = [isol[knob]['randread'] for _ in range(len(weights))]
                    for i in range(len(rates)):
                        if 'bs' in js['jobs'][i]['job options'] and '65536' in js['jobs'][i]['job options']['bs']:
                            rates[i] = isol[knob]['64k']
                        elif 'bs' in js['jobs'][i]['job options'] and '262' in js['jobs'][i]['job options']['bs']:
                            rates[i] = isol[knob]['256k']
                        elif 'rw' in js['jobs'][i]['job options'] and js['jobs'][i]['job options']['rw'] == 'read':
                            rates[i] = isol[knob]['seqread']
                        elif 'rw' in js['jobs'][i]['job options'] and js['jobs'][i]['job options']['rw'] == 'randwrite':
                            rates[i] = isol[knob]['randwrite']
                        elif 'rw' in js['jobs'][i]['job options'] and js['jobs'][i]['job options']['rw'] == 'randrw':
                            rates[i] = isol[knob]['mixed']
                            if 'rwmixread' in js['jobs'][i]['job options']:
                                rates[i] = isol[knob]['mixed90']  
                    try:
                        jains = proportional_slowdown_jains(vs, weights, rates)
                        subyp.append(jains)
                    except:
                        subyp.append(0)
                    jains2 = jains_fairness_index_weighted(vs, weights)
                    suby.append(jains2)
                    bwsum = sum(vs) / (1024 * 1024)
                except:
                    pass                
            jains = avg(subyp)
            jains2 = avg(suby)
            yp.append(jains)
            ype.append(statistics.stdev(subyp) if len(subyp) > 1 else 0)
            y.append(jains2)
            ye.append(statistics.stdev(suby) if len(suby) > 1 else 0)
            if jains:
                print(f"    {knob} Jains fairness: {jains} (PS) or {jains2} (LOAD) @ BW sum {bwsum} GiB/s")
            else:
                print(f"    {knob} Jains fairness: - (PS) or - (LOAD) @ BW sum - GiB/s [not measured]")
        
        for yy, yye, name in [(y, ye, "load"), (yp, ype, "proportional")]:
            fig, ax = plt.subplots()
            colors = ['black', ROSE, CYAN, SAND, TEAL, MAGENTA]
        
            plt.bar(LABELS, yy, yerr=yye, color=colors)

            plt.ylim(0, 1)
            #plt.xlabel("Knob")
            plt.ylabel("Jains fairness")
            plt.grid(axis='y')
            plt.xticks(rotation=45, ha='right')

            # Save plot       
            os.makedirs(f'./plots', exist_ok = True)
            fig.savefig(f'./plots/{experiment}-{numjobs}-{name}.pdf', bbox_inches="tight")
            print(experiment, numjobs, name)

            if name == "load" and experiment in ["saturated", "saturatedw", "requestsizelarge"] and numjobs == 16:
                yo.append(yy)
                yoe.append(yye)

fig, axes = plt.subplots(1, 3, sharex=True, sharey=True)
colors = ['black', ROSE, CYAN, SAND, TEAL, MAGENTA]

for i, lyo in enumerate(yo):      
    axes[i].bar(LABELS, lyo, yerr=yoe[i], color=colors)

    #axes[i].ylim(0, 1)
    #plt.xlabel("Knob")
    #plt.ylabel("Jains fairness")
    #plt.grid(axis='y')
    #plt.xticks(rotation=45, ha='right')

axes[0].set(ylabel="Jain's fairness")

# Save plot       
os.makedirs(f'./plots', exist_ok = True)
fig.savefig(f'./plots/merged.pdf', bbox_inches="tight")

