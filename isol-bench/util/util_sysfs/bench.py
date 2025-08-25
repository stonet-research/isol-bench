import os

from .nvme import *

def get_nvmedev() -> NVMeDevice:
    nvme_path='tmp/testdrive'
    if not os.path.exists(nvme_path):
        raise ValueError("No nvme drive specified, please check the README.md")
    with open(nvme_path, "r") as f:
        return find_nvme_with_eui(f.readline().strip())

def proportional_slowdown(l: list[float], isol: list[float]):
    return [ll / lisol for ll, lisol in zip(l, isol)]

def jains_fairness_index_weighted(l: list[float], w: list[int]):
    if len(l) != len(w):
        raise ValueError("Incorrect args")
    n = len(l)
    lw = [ll / ww for ll, ww in zip(l,w)]
    f = (sum(lw) ** 2) / (n * sum([llw**2 for llw in lw]))
    return f

def proportional_slowdown_jains(l: list[float], w: list[int], isol: list[float]):
    pc = proportional_slowdown(l, isol)
    #print(pc, isol, l, w)
    return jains_fairness_index_weighted(pc, w)
