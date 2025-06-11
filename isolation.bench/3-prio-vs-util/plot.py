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

KNOBS = ["iocost", "mq", "mq2", "bfq2"]
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

for experiment in ["tapps", "tapps_joined"]:
    for knob in KNOBS:
        fig, ax = plt.subplots()
        
        plt.xlabel("Aggregated Bandwidth (GiB/s)")
        plt.ylabel("LC-app latency (us)")
        plt.grid(axis='y')
        # plt.xticks(rotation=45, ha='right')

        if knob == "iocost":
            plt.xlim(0, 2.3)
            plt.ylim(0, 100)
            
            for weight in [0, 1]:
                xa = []
                ya = []
                
                for i in range(weight, 31, 2):
                    filename = f'./out/{nvme_device.eui}/{experiment}-{knob}-9-{i}.json'
                    try:
                        js = parse_fio(filename)
                        
                        bws = [float(j['read']['bw_mean']) + float(j['write']['bw_mean'])for j in js['jobs']]
                        bwsum = sum(bws) / (1024 * 1024)
                        p99 = js['jobs'][0]['read']['clat_ns']['percentile']['99.000000'] / 1000

                        xa.append(bwsum)
                        ya.append(p99)
                    except:
                        pass

                #plt.plot(xa, ya, color=colors[weight], label=f"w: {'10,000' if weight else '1'}", markersize=8, marker='o')
                plt.scatter(xa, ya, color=colors[weight], label=f"w: {'10,000' if weight else '1'}")
            
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
        elif knob == "bfq2":
            plt.xlim(0, 2.3)
            plt.ylim(0, 1000)
            
            xa = []
            ya = []
            
            for i in range(weight, 11, 1):
                filename = f'./out/{nvme_device.eui}/{experiment}-{knob}-9-{i}.json'
                try:
                    js = parse_fio(filename)
                    
                    bws = [float(j['read']['bw_mean']) + float(j['write']['bw_mean'])for j in js['jobs']]
                    bwsum = sum(bws) / (1024 * 1024)
                    p99 = js['jobs'][0]['read']['clat_ns']['percentile']['99.000000'] / 1000

                    xa.append(bwsum)
                    ya.append(p99)
                except:
                    pass

            plt.scatter(xa, ya, color=colors[0], label=f"io.weight: {'10,000' if weight else '1'}")
    
        elif knob == "mq" or knob == "mq2":
            plt.xlim(0, 2.3)
            plt.ylim(0, 3 if experiment == "tapps_joined" else 1000) 

            l = [cgroups.IOPriorityClass.IDLE, cgroups.IOPriorityClass.RESTRICT_TO_BE, cgroups.IOPriorityClass.PROMOTE_TO_RT]
            o = list(itertools.product(l, l))

            for i in range(0, 9, 1):
                xa = []
                ya = []

                for j in range(0, 3, 1): 
                    filename = f'./out/{nvme_device.eui}/{experiment}-{knob}-9-{i + 8 * j}.json'
                    try:
                        js = parse_fio(filename)
                        
                        bws = [float(j['read']['bw_mean']) + float(j['write']['bw_mean'])for j in js['jobs']]
                        bwsum = sum(bws) / (1024 * 1024)
                        p99 = js['jobs'][0]['read']['clat_ns']['percentile']['99.000000'] / 1000
                        bwlc = bws[0] / (1024 * 1024)

                        xa.append(bwsum)
                        if "_joined" in experiment: 
                            ya.append(bwlc)
                        else:
                            ya.append(p99)
                    except:
                        pass
                print(o[i], xa, ya)
                label = f'{o[i][0]}'.split('.')[1].split('_')[-1] + '-' + f'{o[i][1]}'.split('.')[1].split('_')[-1] 
                plt.scatter(xa, ya, color=colors[i % len(colors)], label=label)
                plt.legend(ncol=2)

        # Save plot       
        print(f"{experiment}-{knob}")
        os.makedirs(f'./plots', exist_ok = True)
        fig.savefig(f'./plots/{experiment}-{knob}.pdf', bbox_inches="tight")


