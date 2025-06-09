import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'util')))

import csv
import json
import datetime as dt
import os.path
import argparse

from util_sysfs.bench import *
from util_sysfs.perf import get_perf_cycles
from plot_utils import *
import matplotlib.pyplot as plt

KNOBS = ["none", "bfq", "mq", "iomax", "iolat", "iocost"]
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
    numjobss = [32, 64, 128, 256] if not "write" in experiment else [256]
    if "unsaturated" in experiment:
        numjobss = [2, 4]
    for numjobs in numjobss:
        print(numjobs)
        y = []
        yp = []
        for knob in KNOBS:
            filename = f'./out/{nvme_device.eui}/{experiment}-{knob}-{numjobs}.json'
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
                jains = proportional_slowdown_jains(vs, weights, rates)
                jains2 = jains_fairness_index_weighted(vs, weights)
                bwsum = sum(vs) / (1024 * 1024)
                print(f"    {knob} Jains fairness: {jains} (PS) or {jains2} (LOAD) @ BW sum {bwsum} GiB/s")
                yp.append(jains)
                y.append(jains2)
            except:
                print(f"    {knob} Jains fairness: - (PS) or - (LOAD) @ BW sum - GiB/s [not measured]")
                y.append(0)
                yp.append(0)

        for yy, name in [(y, "load"), (yp, "proportional")]:
            fig, ax = plt.subplots()
            colors = ['black', ROSE, CYAN, SAND, TEAL, MAGENTA]
        
            plt.bar(KNOBS, yy, color=colors)

            plt.ylim(0, 1)
            #plt.xlabel("Knob")
            plt.ylabel("Jains fairness")
            plt.grid(axis='y')

            # Save plot       
            os.makedirs(f'./plots', exist_ok = True)
            fig.savefig(f'./plots/{experiment}-{numjobs}-{name}.pdf', bbox_inches="tight")
