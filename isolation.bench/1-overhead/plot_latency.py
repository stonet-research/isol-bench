import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'util')))

import csv
import json
import matplotlib.pyplot as plt
import datetime as dt
import os.path
import argparse

from util_sysfs.bench import *

PLOT_ELEMENTS = {
    'none': 'no knob',
    'iomax': 'io.max',
    'iocost': 'io.cost',
    'iolat': 'io.latency',
    'mq': 'MQ-DL',
    'bfq': 'BFQ',
    # add your own here
}

def parse_fio_json(filename):
    j = {}
    with open(filename) as f:
        j = json.load(f)
    return j

def avg(ar):
    return sum(ar) / len(ar)

def parse_sar(filename):
    with open(filename) as file:
        usr = []
        sys = []

        tmp = []
        for line in file:
            l = line.split()
            try:
                if l[2] == "2":
                    v = float(l[3]) + float(l[5])
                    #v = v + float(l[6])
                    #print(l[5], l[6])
                    tmp.append(v)
            except:
                continue
    return avg(tmp[28:90]) / 100

def parse_pidstat(filename):
    lpidtemp = []
    with open(filename) as file:
        usr = []
        sys = []

        tmp = []
        for line in file:
            l = line.split()
            if 'CPU  Command' in line and len(tmp):
                lpidtemp.append(sum(tmp))
                tmp = []
            if len(l) > 2 and '-' in l[3]:
                continue 
            try:
                tmp.append(float(l[5]) + float(l[6]))
            except:
                continue
        if len(tmp):
            lpidtemp.append(sum(tmp))
    lpidtemp = lpidtemp[28:90]
    return avg(lpidtemp) / 100

def set_font(size):
    text_font_size = size
    marker_font_size = size
    label_font_size = size
    axes_font_size = size

    plt.rc('pdf', use14corefonts=True, fonttype=42)
    plt.rc('ps', useafm=True)
    plt.rc('font', size=text_font_size, weight="bold", family='serif', serif='cm10')
    plt.rc('axes', labelsize=axes_font_size,labelweight="bold")    
    plt.rc('xtick', labelsize=label_font_size)    
    plt.rc('ytick', labelsize=label_font_size)    
    plt.rc('legend', fontsize=label_font_size)  
set_font(21)

nvme_drive = get_nvmedev()

def to_one_digit(v):
    return round(v*10)/10 

def plot_cdf(knobs_to_plot):
    for active in [True, False]:
        for jobs in [1, 2, 4, 8, 16, 32, 64, 128, 256]:
            fig, ax = plt.subplots()

            i = 0
            for knob in knobs_to_plot:
                j = parse_fio_json(f'./out/{nvme_drive.eui}/{knob}/{active}-{jobs}.json')
                percentile = j['jobs'][0]['read']['clat_ns']['percentile']

                x = [float(x) / 100. for x in percentile.keys()]
                v = [ y / 1000 for y in list(percentile.values())]

                plt.plot(v, x, label=PLOT_ELEMENTS[knob], linewidth=4, linestyle='solid', marker='o')

                if jobs >= 128:
                    ax.annotate(f'{PLOT_ELEMENTS[knob]}: {to_one_digit(v[-2])}', xy=(3200, 0.95), xytext=(3000, 0.55-0.1*i), arrowprops = dict(facecolor ='black',
                                  shrink = 0.05) if i == 0 else None,)
                else:
                    ax.annotate(f'{PLOT_ELEMENTS[knob]}: {to_one_digit(v[-2])}', xy=(v[-2], 0.95), xytext=(200 + ( (i // 3) * 500), 0.75-0.1*i + (0.3 * (i // 3))), arrowprops = dict(facecolor ='black',
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
            plt.hlines(y=0.95, xmin=0, xmax=10000, linewidth=2, color='r')

            plt.ylabel("Cumulative probability")
            fig.savefig(f"./plots/cdf-{active}-{jobs}.pdf", bbox_inches="tight")

def plot_cpu(knobs_to_plot): 
    for active in [True, False]:

        fig, ax = plt.subplots()

        jobs = [1, 2, 4, 8, 16, 32, 64, 128, 256] 
        for knob in knobs_to_plot:
            v = []
            for jj in jobs:
                if (knob == 'none' or knob == "mq") and not active:
                    s = parse_sar(f'./out/{nvme_drive.eui}/{knob}/{active}-{jj}.sar')
                    print(knob, jj, s)
                    v.append(s)
                elif knob == "bfq" and not active:
                    so = parse_sar(f'./out/{nvme_drive.eui}/{knob}/{active}-{jj}.sar')
                    s = parse_pidstat(f'./out/{nvme_drive.eui}/{knob}/{active}-{jj}.pidstat')
                    print(knob, s, so)
                    v.append(s)
                else:
                    j = parse_fio_json(f'./out/{nvme_drive.eui}/{knob}/{active}-{jj}.json')
                    usr_cpu = j['jobs'][0]['usr_cpu']
                    sys_cpu = j['jobs'][0]['sys_cpu']
                    #print(usr_cpu * jj, sys_cpu * jj)
                    v.append( (usr_cpu + sys_cpu) * jj / 100)
            plt.plot([xx + 1 for xx in range(len(jobs))], v, label=PLOT_ELEMENTS[knob], linewidth=4, linestyle='solid', marker='o')
            #print(v)

        plt.xticks(range(len(jobs) + 1), [0] + jobs)
        plt.xlabel("#processes")
        plt.ylabel("CPU utilization (%)")
        plt.xlim(0, len(jobs) + 1)
        plt.yticks([0, 0.25, 0.5, 0.75, 1.00], [0, 25, 50, 75, 100])
        plt.ylim(0, 1.1)
        plt.grid()
        #plt.legend(ncol=2)
            
        fig.savefig(f"./plots/cpu-{active}.pdf", bbox_inches="tight")

def main(knobs_to_plot):
    plot_cpu(knobs_to_plot)
    plot_cdf(knobs_to_plot)

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
    
    main(knobs_to_plot)

