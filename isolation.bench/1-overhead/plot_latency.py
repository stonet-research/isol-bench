import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'util')))

import csv
import json
import datetime as dt
import os.path
import argparse

from util_sysfs.bench import *
from plot_utils import *
import matplotlib.pyplot as plt

PLOT_ELEMENTS = {
    'none': 'no knob',
    'iomax': 'io.max',
    'iocost': 'io.cost',
    'iolat': 'io.latency',
    'mq': 'MQ-DL',
    'bfq': 'BFQ',
    # add your own here
}

NUMJOBS = [2**i for i in range(0,9)]
LAT_STATS = ["fio", "sar", "pidstat"]

def parse_fio_json(filename):
    j = {}
    with open(filename) as f:
        j = json.load(f)
    return j

def avg(ar):
    return sum(ar) / len(ar)

def parse_sar_cpu_avg(filename):
    tmp = parse_sar(filename, "2")[28:90]
    return avg(tmp) / 100

def parse_pidstat_cpu_avg(filename):
    tmp = parse_pidstat(filename)[28:90]
    return avg(tmp) / 100

def parse_fio_cpu_avg(filename, jj:int):
    j = parse_fio_json(filename)
    usr_cpu = j['jobs'][0]['usr_cpu']
    sys_cpu = j['jobs'][0]['sys_cpu']
    return (usr_cpu + sys_cpu) * jj / 100

def resolve_path(knob, active, jobs, cgroups_active):
    return f'./out/{nvme_drive.eui}/{knob}/{active}-{jobs}-{cgroups_active}'

def plot_cdf(nvme_drive, knobs_to_plot, active = True, cgroups_active = True, lat_stat = "sar"):
    """ Plot a CDF plot of the latency """
    
    def to_one_digit(v):
        return round(v*10)/10 

    for jobs in NUMJOBS:
        fig, ax = plt.subplots()


        outname = f"./plots/{nvme_drive.eui}/cdf-{lat_stat}-{'active' if active else 'inactive'}-{'intercgroups' if cgroups_active else 'intracgroups'}-{jobs}.pdf"

        i = 0
        for knob in knobs_to_plot:
            j = parse_fio_json(f'{resolve_path(knob, active, jobs, cgroups_active)}.json')
            percentile = j['jobs'][0]['read']['clat_ns']['percentile']

            x = [float(x) / 100. for x in percentile.keys()]
            v = [ y / 1000 for y in list(percentile.values())]

            plt.plot(v, x, label=PLOT_ELEMENTS[knob], linewidth=4, linestyle='solid', marker='o')

            if jobs >= 128:
                ax.annotate(f'{PLOT_ELEMENTS[knob]}: {to_one_digit(v[-4])}', xy=(3200, 0.99), xytext=(3000, 0.55-0.1*i), arrowprops = dict(facecolor ='black',
                                shrink = 0.05) if i == 0 else None,)
            else:
                ax.annotate(f'{PLOT_ELEMENTS[knob]}: {to_one_digit(v[-4])}', xy=(v[-4], 0.99), xytext=(200 + ( (i // 3) * 500), 0.75-0.1*i + (0.3 * (i // 3))), arrowprops = dict(facecolor ='black',
                                shrink = 0.05) if i == 0 else None,)
            i = i + 1

        if jobs >= 128:
            plt.xticks(range(0, 6000, 1000), ['0'] + [f'{xx},000' for xx in range(1,6)])
            plt.xticks(range(0, 7000, 1000), ['0'] + [f'{xx}' for xx in range(1,7)])
            plt.xlabel("Latency (ms)")
            plt.xlim(0, 6000)
        else:  
            plt.xticks(range(0, 1500, 300), list(range(0, 1200, 300)) + ['1,200'] )
            plt.xlabel("Latency (us)")
            plt.xlim(0, 1200)
        if jobs == 1:
            plt.legend(ncol=2)
        
        plt.yticks([0, 0.25, 0.5, 0.75, 1.00])
        plt.ylim(0, 1.1)
        plt.grid()
        plt.hlines(y=0.99, xmin=0, xmax=10000, linewidth=2, color='r')
        plt.ylabel("Cumulative probability")

        os.makedirs(f'./plots', exist_ok = True)
        os.makedirs(f'./plots/{nvme_drive.eui}', exist_ok = True)
        fig.savefig(outname, bbox_inches="tight")

def plot_cpu(nvme_drive, knobs_to_plot, active = True, cgroups_active = True, lat_stat = "sar"): 
    """ Create a CPU utilization plot """
    
    outname = f"./plots/{nvme_drive.eui}/cpu-{lat_stat}-{'active' if active else 'inactive'}-{'intercgroups' if cgroups_active else 'intracgroups'}.pdf"
    x = [xx + 1 for xx in range(len(NUMJOBS))]
    lines = []

    # Collect data
    for knob in knobs_to_plot:
        y = []
        for jj in NUMJOBS:
            file_preamble = f'./out/{nvme_drive.eui}/{knob}/{active}-{jj}-{cgroups_active}' 
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
    for (name, y) in lines:    
        plt.plot(x, y, label=PLOT_ELEMENTS[name], linewidth=4, linestyle='solid', marker='o')
    plt.xticks(range(len(NUMJOBS) + 1), [0] + NUMJOBS)
    plt.xlim(0, len(NUMJOBS) + 1)    
    plt.yticks([0, 0.25, 0.5, 0.75, 1.00], [0, 25, 50, 75, 100])
    plt.ylim(0, 1.1)
    plt.xlabel("#processes")
    plt.ylabel("CPU utilization (%)")
    plt.grid()
    plt.legend(ncol=1, loc='lower right')

    # Save plot       
    os.makedirs(f'./plots', exist_ok = True)
    os.makedirs(f'./plots/{nvme_drive.eui}', exist_ok = True)
    fig.savefig(outname, bbox_inches="tight")

def main(knobs_to_plot, nvme_drive):
    set_standard_font()
    for active in [True, False]:
        for cgroups_active in [True, False]:
            for lat_stat in ["fio", "sar", "pidstat"]:
                plot_cpu(nvme_drive, knobs_to_plot, active, cgroups_active, lat_stat)
                plot_cdf(nvme_drive, knobs_to_plot, active, cgroups_active, lat_stat)

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
