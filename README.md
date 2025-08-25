# isol-bench

This repository is the home of isol-bench, a tool to evaluate storage performance isolation desiderata in GNU/Linux.
Currently it has builtin support to evaluate I/O schedulers and cgroups, with knobs for io.max, io.cost, io.latency, io.prio.class and io.bfq.weight.
isol-bench was used in the IISWC'25 publication "Does Linux Provide Performance Isolation for NVMe SSDs? Configuring cgroups for I/O Control in the NVMe Era".
Below we detail the installation procedures and dependencies, and tne current isolation benchmarks.

# dependencies and installation

## OS

First check OS compatability. Linux 6.9+ is required and BLK_CGROUP_IOLATENCY needs to be enabled. For reproducibility we have linked our kernel config and commit in the `kernel-setup` directory along with an installation script.

## Benchmark

First install fio:

```bash
apt-get update
apt-get install -y wget git build-essential zlib1g-dev libnuma-dev libaio-dev

git submodule init
git submodule update --recursive

pushd isol-bench/dependencies/fio
./configure
make -j
popd
```

Check Python version, we only tested on one version:

```bash
python3 --version
## Python 3.10.12
```

Install plotting libs

```bash
pip3 install matplotlib
```

# benchmarks

All benchmarks are found in the isol-bench dir. For every test there is a subdir with a readme.

1-overhead: test overhead of a knob in latency, bandwidth, CPU, memory

2-fairness: test fairness capabilities of a knob

3-prio-versus-util: give the pareto front capabilities of a knob in latency/bandwidth prio and SSD bandwidth utilization

4-bursts: evaluate the response time of prioritization (continuation of benchmark 3)
