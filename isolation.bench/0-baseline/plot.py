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

def plot_iomax_example():
    fig, ax = plt.subplots()

    for enabled in [True]:
        st = 'solid' if enabled else 'dashed'

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.max-{enabled}-0_bw.1.log')
        plt.plot([xx + 0 for xx in x], kib_to_mib(y), color='#AA4499', label=f'A - io.max @ 1500 MiB/s', linestyle=st, linewidth=4)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.max-{enabled}-1_bw.2.log')
        plt.plot([xx + 10 for xx in x], kib_to_mib(y), color='#117733', label=f'B - io.max @ 500 MiB/s', linestyle=st, linewidth=4)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.max-{enabled}-2_bw.3.log')
        plt.plot([xx + 20 for xx in x], kib_to_mib(y), color='#DDCC77', label=f'C - io.max @ 500 MiB/s', linestyle=st, linewidth=4)

    plt.xticks(list(range(0, 90, 10)))
    plt.grid()

    plt.ylim(0,2500)
    plt.xlabel("Time (s)")
    plt.ylabel("Throughput (MiB/s)")
    plt.legend(loc=(0.01, 0.62))
    fig.savefig(f'./plots/io.max.pdf', bbox_inches="tight")

def plot_ioprio_mq_example():
    fig, ax = plt.subplots()

    for enabled in [True]:
        st = 'solid' if enabled else 'dashed'

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.prio_class+mq-{enabled}-0_bw.1.log')
        plt.plot([xx + 0 for xx in x], kib_to_mib(y), color='#AA4499', label=f'A - promote-to-rt', linestyle=st, linewidth=4)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.prio_class+mq-{enabled}-2_bw.3.log')
        plt.plot([xx + 20 for xx in x], kib_to_mib(y), color='#DDCC77', label=f'B - restrict-to-be', linestyle=st, linewidth=4)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.prio_class+mq-{enabled}-1_bw.2.log')
        plt.plot([xx + 10 for xx in x], kib_to_mib(y), color='#117733', label=f'C - idle', linestyle=st, linewidth=4)

    plt.xlim(0, 90)
    plt.xticks(list(range(0, 100, 10)))
    plt.grid()

    plt.ylim(0,2500)
    plt.xlabel("Time (s)")
    plt.ylabel("Throughput (MiB/s)")
    plt.legend(loc=(0.01, 0.62))
    fig.savefig(f'./plots/io.priomq.pdf', bbox_inches="tight")

def plot_ioprio_bfq_example():
    fig, ax = plt.subplots()

    for enabled in [True]:
        st = 'solid' if enabled else 'dashed'

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.prio_class+bfq-{enabled}-0_bw.1.log')
        plt.plot([xx + 0 for xx in x], kib_to_mib(y), color='#AA4499', label=f'A - promote-to-rt', linestyle=st, linewidth=4)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.prio_class+bfq-{enabled}-2_bw.3.log')
        plt.plot([xx + 20 for xx in x], kib_to_mib(y), color='#DDCC77', label=f'B - restrict-to-be', linestyle=st, linewidth=4)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.prio_class+bfq-{enabled}-1_bw.2.log')
        plt.plot([xx + 10 for xx in x], kib_to_mib(y), color='#117733', label=f'C - idle', linestyle=st, linewidth=4)

    plt.xlim(0, 90)
    plt.xticks(list(range(0, 100, 10)))
    plt.grid()

    plt.ylim(0,2500)
    plt.xlabel("Time (s)")
    plt.ylabel("Throughput (MiB/s)")
    plt.legend(loc=(0.01, 0.62))
    fig.savefig(f'./plots/io.priobfq.pdf', bbox_inches="tight")

def plot_iowbfq_example():
    fig, ax = plt.subplots()

    for enabled in [True]:
        st = 'solid' if enabled else 'dashed'

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.bfq.weight-{enabled}-0_bw.1.log')
        plt.plot([xx + 0 for xx in x], kib_to_mib(y), color='#AA4499', label=f'A - io.bfq.weight @ 1000', linestyle=st, linewidth=4, zorder=1)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.bfq.weight-{enabled}-2_bw.3.log')
        plt.plot([xx + 20 for xx in x], kib_to_mib(y), color='#DDCC77', label=f'B - io.bfq.weight @ 100', linestyle=st, linewidth=4, zorder=2)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.bfq.weight-{enabled}-1_bw.2.log')
        plt.plot([xx + 10 for xx in x], kib_to_mib(y), color='#117733', label=f'C - io.bfq.weight @ 1', linestyle=st, linewidth=4, zorder=3)

    plt.xlim(0, 90)
    plt.xticks(list(range(0, 100, 10)))
    plt.grid()

    plt.ylim(0,2500)
    plt.xlabel("Time (s)")
    plt.ylabel("Throughput (MiB/s)")
    plt.legend(loc=(0.01, 0.62))
    fig.savefig(f'./plots/io.bfq.weight.pdf', bbox_inches="tight")

def plot_iolatency_example():
    fig, ax = plt.subplots()

    for enabled in [True]:
        st = 'solid' if enabled else 'dashed'

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.latency-{enabled}-0_bw.1.log')
        plt.plot([xx + 0 for xx in x], kib_to_mib(y), color='#AA4499', label=f'A - io.latency @ 20us', linestyle=st, linewidth=4, zorder=1)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.latency-{enabled}-2_bw.3.log')
        plt.plot([xx + 20 for xx in x], kib_to_mib(y), color='#DDCC77', label=f'B - io.latency @ 100us', linestyle=st, linewidth=4, zorder=3)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.latency-{enabled}-1_bw.2.log')
        plt.plot([xx + 10 for xx in x], kib_to_mib(y), color='#117733', label=f'C - io.latency @ 1000us', linestyle=st, linewidth=4, zorder=2)

    plt.xlim(0, 90)
    plt.xticks(list(range(0, 100, 10)))
    plt.grid()

    plt.ylim(0,2500)
    plt.xlabel("Time (s)")
    plt.ylabel("Throughput (MiB/s)")
    plt.legend(loc=(0.01, 0.62))
    fig.savefig(f'./plots/io.latency.pdf', bbox_inches="tight")

def plot_iocost_example():
    fig, ax = plt.subplots()

    for enabled in [True]:
        st = 'solid' if enabled else 'dashed'

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.cost-{enabled}-0_bw.1.log')
        plt.plot([xx + 0 for xx in x], kib_to_mib(y), color='#AA4499', label=f'A', linestyle=st, linewidth=4, zorder=1)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.cost-{enabled}-2_bw.3.log')
        plt.plot([xx + 20 for xx in x], kib_to_mib(y), color='#DDCC77', label=f'B', linestyle=st, linewidth=4, zorder=3)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.cost-{enabled}-1_bw.2.log')
        plt.plot([xx + 10 for xx in x], kib_to_mib(y), color='#117733', label=f'C', linestyle=st, linewidth=4, zorder=2)

    plt.xlim(0, 90)
    plt.xticks(list(range(0, 100, 10)))
    plt.grid()

    plt.ylim(0,2500)
    plt.xlabel("Time (s)")
    plt.ylabel("Throughput (MiB/s)")
    plt.legend(loc=(0.01, 0.62))
    fig.savefig(f'./plots/io.cost.pdf', bbox_inches="tight")

def plot_iocostw_example():
    fig, ax = plt.subplots()

    for enabled in [True]:
        st = 'solid' if enabled else 'dashed'

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.cost+weights-{enabled}-0_bw.1.log')
        plt.plot([xx + 0 for xx in x], kib_to_mib(y), color='#AA4499', label=f'A - io.weight @ 1000', linestyle=st, linewidth=4, zorder=1)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.cost+weights-{enabled}-2_bw.3.log')
        plt.plot([xx + 20 for xx in x], kib_to_mib(y), color='#DDCC77', label=f'B - io.weight @ 100', linestyle=st, linewidth=4, zorder=3)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.cost+weights-{enabled}-1_bw.2.log')
        plt.plot([xx + 10 for xx in x], kib_to_mib(y), color='#117733', label=f'C - io.weight @ 1', linestyle=st, linewidth=4, zorder=2)

    plt.xlim(0, 90)
    plt.xticks(list(range(0, 100, 10)))
    plt.grid()

    plt.ylim(0,2500)
    plt.xlabel("Time (s)")
    plt.ylabel("Throughput (MiB/s)")
    plt.legend(loc=(0.01, 0.62))
    fig.savefig(f'./plots/io.costw.pdf', bbox_inches="tight")

def plot_empty():
    fig, ax = plt.subplots()

    for enabled in [False]:
        st = 'solid'

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.cost-{enabled}-0_bw.1.log')
        plt.plot([xx + 0 for xx in x], kib_to_mib(y), color='#AA4499', label=f'A', linestyle=st, linewidth=4, zorder=1)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.cost-{enabled}-2_bw.3.log')
        plt.plot([xx + 20 for xx in x], kib_to_mib(y), color='#DDCC77', label=f'B', linestyle=st, linewidth=4, zorder=3)

        x, y = parse_fio_bw_log(f'./out/{nvme_drive.eui}/io.cost-{enabled}-1_bw.2.log')
        plt.plot([xx + 10 for xx in x], kib_to_mib(y), color='#117733', label=f'C', linestyle=st, linewidth=4, zorder=2)

    plt.xlim(0, 90)
    plt.xticks(list(range(0, 100, 10)))
    plt.grid()

    plt.ylim(0,2500)
    plt.xlabel("Time (s)")
    plt.ylabel("Throughput (MiB/s)")
    plt.legend(loc=(0.01, 0.62))
    fig.savefig(f'./plots/none.pdf', bbox_inches="tight")

plot_iomax_example()
plot_ioprio_mq_example()
plot_ioprio_bfq_example()
plot_iowbfq_example()
plot_iolatency_example()
plot_iocost_example()
plot_iocostw_example()
plot_empty()