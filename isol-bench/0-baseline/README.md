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

# Execute benchmarks 

Make sure your SSD is filled and pre-conditioned. Then run:
```bash
python3 run.py --help

for knob in none mq bfq iomax iopriomq iopriobfq iobfqweight iolatency iocost iocostw; do
    python3 run.py "--${knob}"  
done 
```

Debug settings during run:
```bash
grep . /sys/fs/cgroup/example-workload-*/io.{prio.class,max,latency,weight,bfq.weight} \
       /sys/fs/cgroup/example-workload-*/*/io.{prio.class,max,latency,weight,bfq.weight} \
       /sys/block/nvme*/queue/scheduler
```

Check output, there should be a ".json" and a ".log" for each knob:
```bash
ls out/${testdrive}/*.{json, log}
```
**NOTE**: 
Note the workloads are read-only, so the drive only needs to be reformatted and preconditioned before the first run.


# Plot benchmarks

```bash
for knob in none mq bfq iomax iopriomq iopriobfq iobfqweight iolatency iocost iocostw; do
    python3 plot.py "--${knob}" 
done

# Check plots, there should be a ".pdf" for each knob
ls plots/${testdrive}/*.pdf
```