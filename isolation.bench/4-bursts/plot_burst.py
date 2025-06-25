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

nvme_device = get_nvmedev()
set_standard_font()

def avg(y):
    return sum(y) / len(y) if len(y) else 0

def parse_fio(filename):
    with open(filename, 'r') as f:
        js = json.load(f)
        return js 

def parse_log(filename):
    x = []
    y = []
    with open(filename, 'r') as f:
        for line in f.readlines():
            l = line.split(',')
            x.append(int(l[0].strip()))
            y.append(int(l[1].strip()))
    return (x,y)

fig, ax = plt.subplots()

for i, knob in enumerate(["none", "iomax", "iolat", "iocost", "bfq2"]):
    filename = f'./out/{nvme_device.eui}/{knob}_lat.1.log'

    x, y = parse_log(filename)
    x = x[:5000]
    y = y[:5000]
        
    plt.plot(x, [yy / 1000 for yy in y], color=["black", ROSE, CYAN, SAND, TEAL][i], label=knob)            
    plt.legend()

    #plt.xlim(0, 2.5)
    plt.xlabel("Time (ms)")
    plt.ylabel("LC-app p99 latency (us)")
    plt.ylim(0, 200) 
    plt.grid()

    os.makedirs(f'./plots', exist_ok = True)

fig.savefig(f'./plots/lc_burst.pdf', bbox_inches="tight")

fig, ax = plt.subplots()

for i, knob in enumerate(["iocost", "iomax", "iolat", "none", "bfq2"]):
    filename = f'./out/{nvme_device.eui}/{knob}_bw.1.log'

    x, y = parse_log(filename)
    x = x[:5000]
    y = y[:5000]
        
    plt.plot(x, [yy / 1024 for yy in y], color=["black", ROSE, CYAN, SAND, TEAL][i], label=knob)            
    plt.legend()

    #plt.xlim(0, 2.5)
    plt.xlabel("Time (ms)")
    plt.ylabel("Batch-app bandwidth (MiB/s)")
    #plt.ylim(0, 1) 
    plt.grid()

    os.makedirs(f'./plots', exist_ok = True)

fig.savefig(f'./plots/batch_burst.pdf', bbox_inches="tight")