import os

from .nvme import *

def get_nvmedev() -> NVMeDevice:
    nvme_path='tmp/testdrive'
    if not os.path.exists(nvme_path):
        raise ValueError("No nvme drive specified, please check the README.md")
    with open(nvme_path, "r") as f:
        return find_nvme_with_eui(f.readline().strip())
