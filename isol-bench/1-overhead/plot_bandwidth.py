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

PLOT_ELEMENTS = {
    'none': 'no knob',
    'iomax': 'io.max',
    'iolat': 'io.latency',
    'iocost': 'io.cost',
    'mq': 'MQ-DL',
    'bfq3': 'BFQ',
    # add your own here
}

NUMJOBS = [1, 3, 5, 7, 9, 11, 13, 15, 17]
LAT_STATS = ["fio", "sar", "pidstat"]

def parse_fio_json(filename):
    j = {}
    with open(filename) as f:
        j = json.load(f)
    return j

def avg(ar):
    return sum(ar) / len(ar)

def parse_sar_cpu_avg(filename):
    tmp = parse_sar(filename, "1-10")[28:90]
    return avg(tmp) / 100

def parse_pidstat_cpu_avg(filename):
    tmp = parse_pidstat(filename)[28:90]
    return avg(tmp) / 100

def parse_fio_cpu_avg(filename, jj:int):
    j = parse_fio_json(filename)
    usr_cpu = j['jobs'][0]['usr_cpu']
    sys_cpu = j['jobs'][0]['sys_cpu']
    return (usr_cpu + sys_cpu) * jj / 100

def resolve_path(knob, disks, jobs, cgroups_active):
    return f'./out/nvme_scaling/{knob}/t-{disks}-{jobs}-{cgroups_active}'

def to_one_digit(v):
        return round(v*10)/10 

def plot_cpu(knobs_to_plot, numdisks, cgroups_active = True, lat_stat = "sar"): 
    """ Create a CPU utilization plot """
    
    outname = f"./plots/nvme_scaling/bw-cpu-{lat_stat}-{numdisks}-{'intercgroups' if cgroups_active else 'intracgroups'}.pdf"
    x = [xx + 1 for xx in range(len(NUMJOBS))]
    lines = []

    # Collect data
    for knob in knobs_to_plot:
        y = []
        for jj in NUMJOBS:
            file_preamble = f'./out/nvmescaling/{knob}/t-{numdisks}-{jj}-{cgroups_active}' 
            if lat_stat == "sar":
                v = parse_sar_cpu_avg(f'{file_preamble}.sar')
            elif lat_stat == "pidstat":
                v = parse_pidstat_cpu_avg(f'{file_preamble}.pidstat')
            elif lat_stat == "fio":
                v = parse_fio_cpu_avg(f'{file_preamble}.json', jj) 
            else:
                raise ValueError("lat_stat not implemented")
            y.append(v)
        lines.append((knob, y))

    # Plot data
    fig, ax = plt.subplots()
    i = 0
    colors = ['black', ROSE, CYAN, SAND, TEAL, MAGENTA]
    markers = ['o', 'v', '^', 'D', 's', "X"]
    for (name, y) in lines:    
        plt.plot(x, y, label=PLOT_ELEMENTS[name], linewidth=4, linestyle='solid', marker=markers[i], color=colors[i], markersize=8)
        i = i + 1
        if numdisks == 1 and lat_stat == "sar":
            print(f"{name}, {y[-1]}")

    plt.hlines(y=10, xmin=0, xmax=10000, linewidth=2, color='r')
    plt.xticks(range(len(NUMJOBS) + 1), [0] + NUMJOBS)
    plt.xlim(0, len(NUMJOBS) + 1)    
    plt.ylim(0, 20)
    plt.xlabel("#batch-apps")
    plt.ylabel("CPU cores utilized (#)")
    plt.grid()
    if numdisks == 1:
        plt.legend(ncol=2, loc='upper left')

    # Save plot       
    os.makedirs(f'./plots', exist_ok = True)
    os.makedirs(f'./plots/nvme_scaling', exist_ok = True)
    fig.savefig(outname, bbox_inches="tight")

def plot_bw(knobs_to_plot, numdisks, cgroups_active = True, lat_stat = "sar"): 
    """ Create a CPU utilization plot """
    
    outname = f"./plots/nvme_scaling/bw-{lat_stat}-{numdisks}-{'intercgroups' if cgroups_active else 'intracgroups'}.pdf"
    x = [xx + 1 for xx in range(len(NUMJOBS))]
    lines = []

    # Collect data
    for knob in knobs_to_plot:
        y = []
        ys = []
        for jj in NUMJOBS:
            file_preamble = f'./out/nvmescaling/{knob}/t-{numdisks}-{jj}-{cgroups_active}' 
            j = parse_fio_json(f'{file_preamble}.json')
            v = (j['jobs'][0]['read']['iops_mean'] * 4096) / (1024 * 1024 * 1024) 
            vs = (j['jobs'][0]['read']['iops_stddev'] * 4096) / (1024 * 1024 * 1024) 
            y.append(v)
            ys.append(vs)
        lines.append((knob, y, ys))
    
        if numdisks == 1 and lat_stat == "sar" and cgroups_active:
            print(f"{knob}, {max(y)}")

    # Plot data
    fig, ax = plt.subplots()
    i = 0
    colors = ['black', ROSE, CYAN, SAND, TEAL, MAGENTA]
    markers = ['o', 'v', '^', 'D', 's', "X"]
    for (name, y, ys) in lines:    
        plt.errorbar(x, y, yerr=ys, label=PLOT_ELEMENTS[name], linewidth=4, linestyle='solid', marker=markers[i], color=colors[i], markersize=8)
        i = i + 1
    plt.xticks(range(len(NUMJOBS) + 1), [0] + NUMJOBS)
    plt.xlim(0, len(NUMJOBS) + 1)    
    #plt.yticks([0, 0.25, 0.5, 0.75, 1.00], [0, 25, 50, 75, 100])
    plt.ylim(0, 10 if numdisks > 1 else 10)
    plt.xlabel("#batch-apps")
    plt.ylabel("Bandwidth (GiB/s)")
    plt.grid()
    if numdisks == 1:
        plt.legend(ncol=2, loc='upper right')

    # Save plot       
    os.makedirs(f'./plots', exist_ok = True)
    os.makedirs(f'./plots/nvme_scaling', exist_ok = True)
    fig.savefig(outname, bbox_inches="tight")


def main(knobs_to_plot, nvme_drive):
    set_standard_font()
    for numdisks in [1, 2, 4, 7]:
        for cgroups_active in [True]:
            for lat_stat in ["fio", "sar", "pidstat"]:
                plot_cpu(knobs_to_plot, numdisks, cgroups_active, lat_stat)
            plot_bw(knobs_to_plot, numdisks, cgroups_active)
        #plot_cdf(nvme_drive, knobs_to_plot, active, cgroups_active, lat_stat)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plot example script data"
    )

    for key in PLOT_ELEMENTS.keys():
        parser.add_argument(f"--{key}", type=bool, required=False, default=False)
    args = parser.parse_args()

    # Determine knobs to plot
    knobs_to_plot = []
    for arg, val in vars(args).items():
        if arg not in PLOT_ELEMENTS:
            raise ValueError(f"Knob {arg} not known")
        elif val:
            knobs_to_plot.append(arg)

    if not len(knobs_to_plot):
        knobs_to_plot = list(PLOT_ELEMENTS.keys())

    nvme_drive = get_nvmedev()
    main(knobs_to_plot, nvme_drive)
