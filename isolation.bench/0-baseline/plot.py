import csv
import matplotlib.pyplot as plt
import datetime as dt
import os.path

def parse_fio_bw_log(filename):
    x = []
    y = []
    with open(filename, 'r') as file:
        rows = csv.reader(file)
        for row in rows:
            if len(row) < 2:
                continue
            x.append(int(row[0]) // 1000)
            y.append(int(row[1]))
    return x, y

def kib_to_mib(y):
    return [yy / 1024 for yy in y]

fig, ax = plt.subplots()

for enabled in [True, False]:
    st = 'solid' if enabled else 'dashed'

    x, y = parse_fio_bw_log(f'./out/io.max-{enabled}-0_bw.1.log')
    plt.plot(x, kib_to_mib(y), color='#117733', label=f'Low-priority workload {enabled}', linestyle=st, linewidth=2)

    x, y = parse_fio_bw_log(f'./out/io.max-{enabled}-1_bw.2.log')
    plt.plot([xx + 20 for xx in x], kib_to_mib(y), color='#AA4499', label=f'High-priority workload {enabled}', linestyle=st, linewidth=2)

plt.ylim(0,2200)
plt.xlabel("Time (s)")
plt.ylabel("Throughput (MiB/s)")
plt.legend()
fig.savefig(f'./plots/io.max.pdf')