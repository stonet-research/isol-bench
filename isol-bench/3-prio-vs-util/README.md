# Register NVMe drive with eui64

We use eui64 to ensure we get the same NVMe for an experiment, even on reboot. Run the following once for each NVMe drive to test.
Note that uuid or puuid do not work here as we potentially want to reformat/overwrite the drive contents.

When changing the drive to test on, run:

```bash
# Make sure you are in the README.md's directory
drive=/dev/nvmeXnY
../util/register_nvme.sh ${drive}
```

# Sequence of tests

## Experiments

1. Below saturation: Scale up tenants while staying below saturation point, what is the fairness? Is there a difference between proportional and non-proportional fairness?
2. Past saturation point: scale up from {saturation point}--32 in powers of 2 what is the fairness?
3. Past saturation point with unfair app output: scale up from {saturation point}--32 and give some apps more I/O. Can one app steal?
4. Weights, are weights accounted for. Repeat (2) with weights
5. Request-size: Now repeat (2) and give half apps a large request size (we do both 64k and 256K) but the same "fio rate". Does fairness change due to request size?
6. Writes+GC: Now repeat (2) for a random-write workload
7. Reads+GC: Try various mixes of reads and writes.

Final results with:

```bash
python3 prio.py 
```

Debug helpers:

```bash
grep . /sys/fs/cgroup/{lc,be}-workload.slice/{io.prio.class,*/io.prio.class}
```

# Analyze and plot

```bash
python3 plot.py 
```
