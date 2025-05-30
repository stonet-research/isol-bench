import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'util')))

import csv
import matplotlib.pyplot as plt
import datetime as dt
import os.path

from util_sysfs.bench import *

def parse_fio_bw_log(filename):
    x = []
    y = []

    with open(filename, "r") as file:
        rows = csv.reader(file)
        first = True 
        
        # determine points
        for row in rows:
            if first:
                x1 = int(row[0]) // 100
                first = False
            xe = int(row[0]) // 100
        x = [float(xx) / 10. for xx in range((xe + 1))]
        y = [0] * len(x)

    with open(filename, 'r') as file:
        rows = csv.reader(file)

        # insert points
        for row in rows:
            if len(row) < 2:
                continue
            xx = int(row[0]) // 100
            y[xx] = int(row[1])
    return x, y

def kib_to_mib(y):
    return [yy / 1024 for yy in y]

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

def example_plot(file_out: str, preamble: str, labels: list[str]):
    if len(labels) != 3:
        raise ValueError("Invalid label count")

    fig, ax = plt.subplots()

    cs = ['#AA4499', '#117733', '#DDCC77']

    for i in range(3):
        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/{preamble}-{i}_bw.{i+1}.log')
        plt.plot([xx + i * 10 for xx in x], kib_to_mib(y), color=cs[i], label=labels[i], linestyle='solid', linewidth=4)

        plt.text(x[0] + i * 10 + 1, kib_to_mib(y)[1] + 75, labels[i][0], ha="center", va="center",
             bbox = dict(boxstyle=f"circle,pad=0.1", fc='white', edgecolor=cs[i], linewidth=4)) 
        
        plt.plot(x[-1] + i * 10, kib_to_mib(y)[-1], marker='>', color=cs[i], markersize=13) 

    plt.xlim(0, 90)
    plt.xticks(list(range(0, 100, 10)))
    plt.grid()

    plt.ylim(0,2500)
    plt.xlabel("Time (s)")
    plt.ylabel("Throughput (MiB/s)")
    plt.legend(loc=(0.01, 0.62))
    fig.savefig(f'./plots/{file_out}.pdf', bbox_inches="tight")

def plot_iomax_example():
    example_plot('io.max', 'io.max-True', ['A - io.max @ 1500 MiB/s', 'B - io.max @ 500 MiB/s', 'C - io.max @ 500 MiB/s'])

def plot_ioprio(scheduler: str):
    example_plot(f'io.prio{scheduler}', f'io.prio_class+{scheduler}-True', ['A - promote-to-rt', 'B - idle', 'C - restrict-to-be'])

def plot_ioprio_mq_example():
    plot_ioprio('mq')

def plot_ioprio_bfq_example():
    plot_ioprio('bfq')

def plot_iowbfq_example():
    example_plot('io.bfq.weight', 'io.bfq.weight-True', ['A - io.bfq.weight @ 1000', 'B - io.bfq.weight @ 1', 'C - io.bfq.weight @ 100'])

def plot_iolatency_example():
    example_plot('io.latency', 'io.latency-True', ['A - io.latency @ 20us', 'B - io.latency @ 1000us', 'C - io.latency @ 100us'])

def plot_iocost_example():
    example_plot('io.cost', 'io.cost-True', ['A', 'B', 'C'])

def plot_iocostw_example():
    example_plot('io.costw', 'io.cost+weights-True', ['A - io.weight @ 1000', 'B - io.weight @ 1', 'C - io.weight @ 100'])

def plot_empty():
    example_plot('none', 'io.cost-False', ['A', 'B', 'C'])

plot_empty()
plot_iomax_example()
plot_ioprio_mq_example()
plot_ioprio_bfq_example()
plot_iowbfq_example()
plot_iolatency_example()
plot_iocost_example()
plot_iocostw_example()
# add your own here
