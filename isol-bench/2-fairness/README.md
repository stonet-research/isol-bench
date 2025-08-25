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

## Setup

Determine SSD saturation point with 4KiB @ 256 apps (batch-apps). We use this point to determine the batch-app configuration.

```bash
# Both points are based on previous experiment
python3 fairness.py --find_saturation=1 --min_saturation=bfq --max_saturation=none
```

Determine the isolated performance (we need proportional slowdown later):

```bash
# Due to various write tests, it can take a day to complete. iolat and mq can be skipped as they do not enable fairness at read tests already
for knob in none bfq mq iomax iocost iolat; do
    python3 fairness.py "--${knob}=1" --isolation=1
done
```

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
python3 fairness.py --numjobs=2 --saturatedspam=1 --saturatedspamw=1 --requestsizelargespam=1 --mixedreadspam=1 --fromiter=0 --iter=5 --none=1 --mq=1 --bfq2=1  --iocost=1  --iomax=1 --iolat=1
python3 fairness.py --numjobs=16 --saturatedspam=1 --saturatedspamw=1 --fromiter=0 --iter=5 --none=1 --mq=1 --bfq2=1  --iocost=1  --iomax=1 --iolat=1
```

Debug helpers:

```bash
# iocost
grep . /sys/fs/cgroup/{io.cost*,example-workload-{0..16}.slice/io.weight}
# bfq and mq
cat /sys/block/nvme*/queue/scheduler
grep . /sys/fs/cgroup/{example-workload-{0..16}.slice/{io.bfq.weight, io.prio.class}}
# iolat
grep . /sys/fs/cgroup/{example-workload-{0..16}.slice/io.latency}
# iomax
grep . /sys/fs/cgroup/{example-workload-{0..16}.slice/io.max}
```

# Analyze and plot

```bash
python3 plot.py 
```
