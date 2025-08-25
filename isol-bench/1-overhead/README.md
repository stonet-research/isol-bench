# Register NVMe drive with eui64

We use eui64 to ensure we get the same NVMe for an experiment, even on reboot. Run the following once for each NVMe drive to test.
Note that uuid or puuid do not work here as we potentially want to reformat/overwrite the drive contents.

When changing the drive to test on, run:

```bash
# Make sure you are in the README.md's directory
drive=/dev/nvmeXnY
../util/register_nvme.sh ${drive}
```

# Execute and plot latency overhead

Make sure your SSD is filled and pre-conditioned. Then run:

```bash
for knob in none bfq3 mq iomax iolat iocost; do 
    for active in "--active=1" ""; do 
        for cg in "--cgroups=1" ""; do 
            python3 run_latency.py "--${knob}=1" ${active} ${cg}; 
        done
    done; 
done
```

Plot:

```bash
python3 plot_latency.py 
```

# Profile CPU for datapoint in latency overhead experiment

This benchmark runs the previous experiment (latency overhead) with additional profiling

```bash
for knob in none bfq3 mq iomax iolat iocost; do 
    for active in "--active=1" ""; do 
        for cg in "--cgroups=1" ""; do 
            python3 run_latency.py "--${knob}=1" ${active} ${cg} --numjobs=256 --perf=1; 
        done
    done; 
done
```

Plot

```bash
python3 plot_latency.py
```

# Bandwidth saturation

DO NOT RUN ON PRODUCTION MACHINE, IT WIPES ALL SSDS!!!

This benchmark finds the saturation point in bandwidth

```bash

for knob in none mq bfq3 iomax iolat iocost; do
    for cg in "--cgroups=1" ""; do 
        python3 run_bandwidth.py "--${knob} ${cg}" 
    done
done
```

Plot:

```bash
python3 plot_bandwidth.py
```

**NOTE**:
This benchmark does not use eui64 and has to be run in one go.
