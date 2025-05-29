import json
from enum import Enum

from .proc import *

class IOScheduler(Enum):
    NONE="none"
    MQ_DEADLINE="mq-deadline"
    BFQ="bfq"
    KYBER="kyber"
    UNKNOWN="unknown"

    @staticmethod
    def from_str(label: str):
        try:
            return  {
                'none': IOScheduler.NONE,
                'mq-deadline': IOScheduler.MQ_DEADLINE,
                'bfq': IOScheduler.BFQ,
                'kyber': IOScheduler.KYBER
            }[label]
        except:
            return IOScheduler.UNKNOWN

class NVMeDevice(object):
    """Wrapper for NVMe devices in GNU/Linux"""

    NVME_SYSPATH="/sys/class/block"

    def __init__(self, devicename):
        self.devicename = devicename

    @property 
    def name(self) -> str:
        return self.devicename

    @property
    def syspath(self) -> str:
        return f"/dev/{self.name}"

    @property
    def address(self) -> str:
        with open(f"{self.NVME_SYSPATH}/{self.devicename}/device/address", "r") as f:
            return f.readline().strip()

    @property
    def eui(self) -> str:
        with open(f"{self.NVME_SYSPATH}/{self.devicename}/eui", "r") as f:
            return f.readline().strip().replace(" ", "")

    @property
    def nsid(self) -> int:
        with open(f"{self.NVME_SYSPATH}/{self.devicename}/nsid", "r") as f:
            return int(f.readline())

    @property
    def major_minor(self) -> int:
        with open(f"{self.NVME_SYSPATH}/{self.devicename}/dev", "r") as f:
            return f.readline().strip()

    @property
    def numa_node(self) -> int:
        with open(f"{self.NVME_SYSPATH}/{self.devicename}/device/numa_node", "r") as f:
            return int(f.readline())

    @property
    def logical_block_size(self) -> int:
        with open(f"{self.NVME_SYSPATH}/{self.devicename}/queue/logical_block_size", "r") as f:
            return int(f.readline())

    @property
    def min_request_size(self) -> int:
        with open(f"{self.NVME_SYSPATH}/{self.devicename}/queue/minimum_io_size", "r") as f:
            return int(f.readline())

    @property    
    def io_scheduler(self) -> IOScheduler:
        sched = ''
        with open(f"{self.NVME_SYSPATH}/{self.devicename}/queue/scheduler", "r") as f:
            sched = f.readline().strip()
        parsed_sched = sched.split('[')[1].split(']')[0]
        return IOScheduler.from_str(parsed_sched)

    @io_scheduler.setter
    def io_scheduler(self, sched: IOScheduler):
        set_sysfs(f"{self.syspath}/{self.devicename}/queue/scheduler", sched.value)

    @io_scheduler.deleter
    def io_scheduler(self):
        self.io_scheduler = IOScheduler.NONE

def __nvme_cmd(cmd):
    return exec_cmd(f'sudo nvme {cmd}')

def __nvme_name_short(name: str) -> str:
    sp = name.split('/')
    return name if len(sp) == 1 else sp[-1]

def nvme_list() -> list[NVMeDevice]:
    try:
        nvmes_json = json.loads(__nvme_cmd('list -o=json'))
        return [NVMeDevice(__nvme_name_short(nvme['DevicePath'])) for nvme in nvmes_json['Devices']]
    except:
        return []

def find_nvme_with_eui(eui: str):
    if len(eui) != 16:
        raise ValueError('invalid eui')
    return next(filter(lambda nvme_candidate: nvme_candidate.eui == eui, nvme_list()))
