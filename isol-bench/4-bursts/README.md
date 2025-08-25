# Register NVMe drive with eui64

We use eui64 to ensure we get the same NVMe for an experiment, even on reboot. Run the following once for each NVMe drive to test.
Note that uuid or puuid do not work here as we potentially want to reformat/overwrite the drive contents.

When changing the drive to test on, run:

```bash
# Make sure you are in the README.md's directory
drive=/dev/nvmeXnY
../util/register_nvme.sh ${drive}
```

# Experiments

```bash
python3 burst.py
python3 plot_burst.py
```
