# Register NVMe drive with eui64

We use eui64 to ensure we get the same NVMe for an experiment, even on reboot. Run the following once for each NVMe drive to test.
Note that uuid or puuid do not work here as we potentially want to reformat/overwrite the drive contents.

When changing the drive to test on, run:
```bash
# Make sure you are in the README.md's directory
drive=/dev/nvmeXnY
../util/register_nvme.sh ${drive}
../util/precondition.sh ${drive}
```
# Execute and plot latency overhead

Make sure your SSD is filled and pre-conditioned. Then run:
```bash
for knob in none mq bfq iomax iopriomq iopriobfq iobfqweight iolatency iocost iocostw; do
    for active in 1 0; do 
        python3 run_latency.py "--${knob} --active=${active}" 
    done
done
```

# Profile CPU for datapoint in latency overhead experiment

This benchmark runs the previous experiment (latency overhead) with additional profiling

```bash
for knob in none mq bfq iomax iopriomq iopriobfq iobfqweight iolatency iocost iocostw; do
    for active in 1 0; do 
        for numbjobs in 1 64 128 256; do
            python3 profiling_wrapper.py "--${knob} --active=${active} --numjobs=${numjobs}" 
        done
    done
done
```

# Bandwidth saturation

This benchmark finds the saturation point in bandwidth

```bash
ssds="nvme0n1,nvme1n1,nvme2n1,nvme3n1,nvme4n1,nvme5n1,nvme7n1"

for knob in none mq bfq iomax iopriomq iopriobfq iobfqweight iolatency iocost iocostw; do
    for active in 1 0; do 
        python3 run_saturation.py "--${knob} --active=${active} --ssds=${ssds}" 
    done
done
```

**NOTE**: 
This benchmark does not use eui64 and has to be run in one go.