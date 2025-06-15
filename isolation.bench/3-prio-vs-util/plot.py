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
import itertools
from util_sysfs import cgroups as cgroups

KNOBS = ["iocost", "iocost2", "iocost3", "mq", "mq2", "bfq2", "iolat", "iomax"]
LABELS = ["io.cost"]
WORKLOADS = {
    'tapps' : 'tapps',
}

nvme_device = get_nvmedev()
set_standard_font()

def avg(y):
    return sum(y) / len(y) if len(y) else 0

def parse_fio(filename):
    with open(filename, 'r') as f:
        js = json.load(f)
        return js 

colors = ['black', ROSE, CYAN, SAND, TEAL, MAGENTA, GREEN, OLIVE, BLUE, 'orange']

numjobs = [5, 9, 65]

iolats = {}
iomaxs = {}
schedulers = {}
iocost2s = {}

experiments = ["tapps", "rq", "access", "rwshort", "rwlong"]
for i in range(len(experiments)):
    experiments.append(f"{experiments[i]}_joined")
for experiment in experiments:
    for knob in KNOBS:
        for numjob in numjobs:
            fig, ax = plt.subplots()
            
            if knob == "iocost":      
                for weight in [0, 1, 2]:
                    xa = []
                    ya = []
                    
                    for i in range(weight, 46, 3):
                        filename = f'./out/{nvme_device.eui}/{experiment}-{knob}-{numjob}-{i}.json'
                        try:
                            js = parse_fio(filename)
                            
                            bws = [float(j['read']['bw_mean']) + float(j['write']['bw_mean'])for j in js['jobs']]
                            bwsum = sum(bws[1:]) / (1024 * 1024)
                            p99 = js['jobs'][0]['read']['clat_ns']['percentile']['99.000000'] / 1000
                            bwlc = bws[0] / (1024 * 1024)

                            xa.append(bwsum)
                            if "_joined" in experiment: 
                                ya.append(bwlc)
                            else:
                                ya.append(p99)
                        except:
                            pass

                    #plt.plot(xa, ya, color=colors[weight], label=f"w: {'10,000' if weight else '1'}", markersize=8, marker='o')
                    print(weight, xa, ya)
                    plt.scatter(xa, ya, color=colors[weight], label=f"w:{['1-8', '1-1', '1-10,000'][weight]}", s=60)
                
            # for weight in [0, 1]:
            #     xa = []
            #     ya = []
            #     
            #     for i in range(weight, 31, 2):
            #         filename = f'./out/{nvme_device.eui}/tapps-{knob}-8-{i+31}.json'
            #         try:
            #              js = parse_fio(filename)
            #             
                #            bws = [float(j['read']['bw_mean']) + float(j['write']['bw_mean'])for j in js['jobs']]
                #           bwsum = sum(bws) / (1024 * 1024)
                #           p99 = js['jobs'][0]['read']['clat_ns']['percentile']['99.000000'] / 1000
        #
        #                   xa.append(bwsum)
        #                  ya.append(p99)
        ##                pass
        #
                    #plt.plot(xa, ya, color=colors[weight+2], label=f"w: {'1,000' if weight else '10'}", markersize=8, marker='o')
        #           plt.scatter(xa, ya, color=colors[weight+2], label=f"w: {'1,000' if weight else '10'}")
            
                
                plt.legend()
            elif knob == "iocost2":            
                xa = []
                ya = []
                
                for i in range(0, 21, 1):
                    filename = f'./out/{nvme_device.eui}/{experiment}-{knob}-{numjob}-{i}.json'
                    try:
                        js = parse_fio(filename)
                        
                        bws = [float(j['read']['bw_mean']) + float(j['write']['bw_mean'])for j in js['jobs']]
                        bwsum = sum(bws[1:]) / (1024 * 1024)
                        p99 = js['jobs'][0]['read']['clat_ns']['percentile']['99.000000'] / 1000
                        bwlc = bws[0] / (1024 * 1024)

                        xa.append(bwsum)
                        if "_joined" in experiment: 
                            ya.append(bwlc)
                        else:
                            ya.append(p99)
                    except:
                        pass
                print(xa, ya)
                
                for ra in range(3):
                    first = ra*7
                    plt.scatter(xa[first:][:7], ya[first:][:7], color=[TEAL, MAGENTA, 'black'][ra], label=f"io.weight: {'10,000' if weight else '1'}", s=60)
                    if numjob == 5 and ra == 1:
                        iocost2s[experiment] = (xa[first:][:7], ya[first:][:7])
                #if numjob == 5:
                #    iocost2s[experiment] = (xa, ya)

            elif knob == "bfq2" or knob == "iolat" or knob == "iomax" or knob == "iocost3":            
                xa = []
                ya = []
                
                for i in range(0, 31, 1):
                    filename = f'./out/{nvme_device.eui}/{experiment}-{knob}-{numjob}-{i}.json'
                    try:
                        js = parse_fio(filename)
                        
                        bws = [float(j['read']['bw_mean']) + float(j['write']['bw_mean'])for j in js['jobs']]
                        bwsum = sum(bws[1:]) / (1024 * 1024)
                        p99 = js['jobs'][0]['read']['clat_ns']['percentile']['99.000000'] / 1000
                        bwlc = bws[0] / (1024 * 1024)

                        xa.append(bwsum)
                        if "_joined" in experiment: 
                            ya.append(bwlc)
                        else:
                            ya.append(p99)
                    except:
                        pass
                print(xa, ya)
                
                mincs = 1
                maxcs = len(xa) + 1 
                cs = [f"{1 - ((i - mincs) / (maxcs - mincs))}" for i in range(1, len(xa)+1)]
                plt.scatter(xa, ya, color='black', label=f"io.weight: {'10,000' if weight else '1'}", s=60)

                if numjob == 5 and knob == "iolat":
                    iolats[experiment] = (xa, ya)
                elif numjob == 5 and knob == "iomax":
                    iomaxs[experiment] = (xa, ya)
                elif numjob == 5 and knob == "bfq2":
                    if not experiment in schedulers:
                         scheduler[experiment] = {}
                    schedulers[experiment][knob] = (xa, ya)

            elif knob == "mq" or knob == "mq2":
                l = [cgroups.IOPriorityClass.IDLE, cgroups.IOPriorityClass.RESTRICT_TO_BE, cgroups.IOPriorityClass.PROMOTE_TO_RT]
                o = list(itertools.product(l, l))
                
                xa = [[], [], []]
                ya = [[], [], []]
                for i in range(0, 9, 1):
                    for j in range(0, 3, 1): 
                        filename = f'./out/{nvme_device.eui}/{experiment}-{knob}-{numjob}-{i + 9 * j}.json'
                        try:
                            js = parse_fio(filename)
                            
                            bws = [float(j['read']['bw_mean']) + float(j['write']['bw_mean'])for j in js['jobs']]
                            bwsum = sum(bws[1:]) / (1024 * 1024)
                            p99 = js['jobs'][0]['read']['clat_ns']['percentile']['99.000000'] / 1000
                            bwlc = bws[0] / (1024 * 1024)

                            starship = cgroups.IOPriorityClass.compare(o[i][0], o[i][1]) + 1
                            print(o[i], starship, p99)
                            xa[starship].append(bwsum)
                            if "_joined" in experiment: 
                                ya[starship].append(bwlc)
                            else:
                                ya[starship].append(p99)
                        except:
                            pass
                
                if numjob == 5 and knob == "mq":
                    if not experiment in schedulers:
                         schedulers[experiment] = {}
                    schedulers[experiment][knob] = ([], [])

                for i, t in enumerate([("Lower", ROSE), ("Equal", SAND), ("Higher", TEAL)]):
                    #print(o[i], xa, ya)
                    #label = f'{o[i][0]}'.split('.')[1].split('_')[-1] + '-' + f'{o[i][1]}'.split('.')[1].split('_')[-1] 
                    plt.scatter(xa[i], ya[i], color=t[1], label=t[0], s=60)
    
                    if numjob == 5 and knob == "mq":
                        schedulers[experiment][knob] = (schedulers[experiment][knob][0] + xa[i], schedulers[experiment][knob][1] + ya[i])
                plt.legend(title="PC-app priority is:", ncol=1)

            plt.xlim(0, 2.5)
            if "_joined" in experiment:
                plt.ylabel("Batch-app Bandwidth (GiB/s)")
                plt.ylim(0, 1) 
            else:
                plt.ylabel("LC-app P99 Latency (us)")
                plt.ylim(0, 1000 if "rq" in experiment else 200) 
                if "mq" in knob and not "_joined" in experiment:
                    plt.ylim(0, 4000)
            plt.xlabel("Aggregated BE-app Bandwidth (GiB/s)")
            plt.grid()
            # plt.xticks(rotation=45, ha='right')

            # Save plot       
            print(f"{experiment}-{knob}")
            os.makedirs(f'./plots', exist_ok = True)
            fig.savefig(f'./plots/{experiment}-{knob}-{numjob}.pdf', bbox_inches="tight")

# Plot merges
for experiment in ["tapps", "tapps_joined", "rq", "rq_joined", "access", "access_joined"]:
    for knob in KNOBS:
        fig, ax = plt.subplots()
        m = []
        for i in range(0, 46, 1):
            filename = f'./out/{nvme_device.eui}/{experiment}-{knob}-9-{i}.json'
            try:
                js = parse_fio(filename)
                rios = js['disk_util'][0]['read_sectors'] / 8
                wios = js['disk_util'][0]['write_sectors'] / 8
                rmerges = js['disk_util'][0]['read_merges']
                wmerges = js['disk_util'][0]['write_merges']

                merges_normalized = 0
                if rios:
                    merges_normalized = merges_normalized + (rmerges / rios)
                if wios:
                    merges_normalized = merges_normalized + (wmerges / wios)
                m.append(merges_normalized)
            except: 
                continue
        
        ax.plot(list(range(len(m))), m, color='gray', linewidth=4, marker='o', markersize=8)
        ax.set_ylabel("merges")
        ax.set_xlabel("iteration")
        plt.grid()
        plt.ylim(0, 1)

        fig.savefig(f'./plots/merges-{experiment}-{knob}.pdf', bbox_inches="tight")


fig, ax = plt.subplots()

for name, label, color in [
    ("tapps", "4KiB Read", TEAL), 
    ("rq", "256KiB Read", 'black'),
    ("rwshort", "4KiB Mixed", MAGENTA)
    ]:
    if name in iolats:
        xa = iolats[name][0]
        ya = iolats[name][1]
        plt.scatter(xa, ya, c=color, label=label, s=60)
plt.legend(title="BE-workload:")
plt.xlim(0, 2.5) 
plt.ylim(0, 1000) 
plt.grid()
plt.xlabel("Aggregated BE-app Bandwidth (GiB/s)")
plt.ylabel("LC-app P99 Latency (us)")
fig.savefig(f'./plots/iolats-merged.pdf', bbox_inches="tight")


fig, ax = plt.subplots()

for name, label, color in [
    ("tapps", "4KiB Read", TEAL), 
    ("rq", "256KiB Read", 'black'),
    ("rwshort", "4KiB Mixed", MAGENTA)
    ]:
    if name in iomaxs:
        xa = iomaxs[name][0]
        ya = iomaxs[name][1]
        plt.scatter(xa, ya, c=color, label=label, s=60)
plt.legend(title="BE-workload:", loc='upper left')
plt.xlim(0, 2.5) 
plt.ylim(0, 1000) 
plt.grid()
plt.xlabel("Aggregated BE-app Bandwidth (GiB/s)")
plt.ylabel("LC-app P99 Latency (us)")
fig.savefig(f'./plots/iomaxs-merged.pdf', bbox_inches="tight")


fig, ax = plt.subplots()

plt.scatter(schedulers['tapps']['mq'][0], schedulers['tapps']['mq'][1], color=TEAL, label='MQ-DL + io.prio.class', s=60)
plt.scatter(schedulers['tapps']['bfq2'][0], schedulers['tapps']['bfq2'][1], color=MAGENTA, label='BFQ + io.bfq.weight', s=60)

plt.legend()
plt.xlim(0, 2.5) 
plt.ylim(0, 1000) 
plt.grid()
plt.xlabel("Aggregated BE-app Bandwidth (GiB/s)")
plt.ylabel("LC-app P99 Latency (us)")
fig.savefig(f'./plots/schedulers-merged.pdf', bbox_inches="tight")

fig, ax = plt.subplots()

plt.scatter(schedulers['tapps_joined']['mq'][0], schedulers['tapps_joined']['mq'][1], color=TEAL, label='MQ-DL + io.prio.class', s=60)
plt.scatter(schedulers['tapps_joined']['bfq2'][0], schedulers['tapps_joined']['bfq2'][1], color=MAGENTA, label='BFQ + io.bfq.weight', s=60)

plt.legend()
plt.xlim(0, 2.5) 
plt.ylim(0, 1) 
plt.grid()
plt.xlabel("Aggregated BE-app Bandwidth (GiB/s)")
plt.ylabel("Batch-app Bandwidth (GiB/s)")
fig.savefig(f'./plots/schedulers-joined-merged.pdf', bbox_inches="tight")



fig, ax = plt.subplots()

print(iocost2s)

plt.scatter(iocost2s['tapps_joined'][0], iocost2s['tapps_joined'][1], color=TEAL, label='4KiB read', s=60)
plt.scatter(iocost2s['rq_joined'][0], iocost2s['rq_joined'][1], color=MAGENTA, label='256KiB read', s=60)
#plt.scatter(iocost2s['access_joined'][0], iocost2s['access_joined'][1], color=SAND, label='BFQ + io.bfq.weight', s=60)
plt.scatter(iocost2s['rwshort_joined'][0], iocost2s['rwshort_joined'][1], color=SAND, label='4KiB write', s=60)

plt.legend()
plt.xlim(0, 2.5) 
plt.ylim(0, 1) 
plt.grid()
plt.xlabel("Aggregated BE-app Bandwidth (GiB/s)")
plt.ylabel("Batch-app Bandwidth (GiB/s)")
fig.savefig(f'./plots/iocost2s-joined-merged.pdf', bbox_inches="tight")