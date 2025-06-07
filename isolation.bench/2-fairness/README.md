# Sequence of tests

## Setup:

Determine SSD saturation point with 4KiB @ 256 apps (batch-apps). We use this point to determine the batch-app configuration.

```bash
# Both points are based on previous experiment
python3 fairness.py --find_saturation=1 --min_saturation=bfq --max_saturation=none
```

## Experiments

1. Below saturation: Scale up tenants from 1--32 while staying below saturation point, what is the fairness? 
1. Past saturation point: scale up from {saturation point}--32 in powers of 2 what is the fairness.
3. Past saturation point with unfair app output: scale up from {saturation point}--32 and give some apps more I/O. Can one app steal? 
4. Weights, are weights accounted for. Repeat (2) with weights
5. Request-size: Now repeat (2) and give each app a different request size but the same "fio rate". Does fairness change due to request size.
6. Writes+GC: Now repeat (2) for a random-write workload
7. Reads+GC: create a shadow workload that triggers GC by random-writes, evaluate fairness on a set of (2).


```bash
for experiment in below_saturation saturated rates weights size write_only rw; do 
    python3 fairness.py --experiment=${experiment}
done
```

Debug helpers:
```bash
grep . /sys/fs/cgroup/{io.cost*,example-workload-{0..256}.slice/io.weight}
```