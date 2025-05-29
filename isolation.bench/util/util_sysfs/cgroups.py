import os
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from .nvme import *
from .proc import *

cgroup_syspath="/sys/fs/cgroup"

@dataclass
class IOMax:
    major_minor: str
    rbps: int | None
    wbps: int | None
    riops: int | None
    wiops: int | None

    def to_str(self) -> str:
        def h(s):
            return "max" if s == None else str(s)
        return f"{self.major_minor} rbps={h(self.rbps)} wbps={h(self.wbps)} riops={h(self.riops)} wiops={h(self.wiops)}"

    @staticmethod
    def from_str(text: str):
        args = text.strip().split(" ")
        if len(args) == 1:
            return None
        major_minor = args[0]
        rbps = wbps = riops = wiops = None
        for arg in args[1:]:
            kv = arg.split("=")
            if kv[1] == "max":
                continue
            if kv[0] == 'rbps':
                rbps = int(kv[1])    
            elif kv[0] == 'wbps':
                wbps = int(kv[1])
            elif kv[0] == 'riops':
                riops = int(kv[1])
            elif kv[0] == 'wiops':
                wiops = int(kv[1])
        return IOMax(major_minor, rbps, wbps, riops, wiops)

@dataclass
class IOCostModel:
    major_minor: str
    ctrl: str 
    model: str
    rbps: int
    rseqiops: int
    rrandiops: int 
    wbps: int
    wseqiops: int 
    wrandiops: int

    def to_str(self) -> str:
        return f"{self.major_minor} ctrl={self.ctrl} model={self.model} rbps={self.rbps} rseqiops={self.rseqiops} rrandiops={self.rrandiops} wbps={self.wbps} wseqiops={self.wseqiops} wrandiops={self.wrandiops}"

    @staticmethod
    def from_str(text: str):
        args = text.strip().split(" ")
        if len(args) == 1:
            return None
        major_minor = args[0]
        ctrl = "user"
        model = "linear"
        rbps = rseqiops = rrandiops = wbps = wseqiops = wrandiops = 0
        for arg in args[1:]:
            kv = arg.split("=")
            if kv[0] == 'ctrl':
                ctrl = kv[1]
            if kv[0] == 'model':
                model = kv[1]
            if kv[0] == 'rbps':
                rbps = int(kv[1])    
            elif kv[0] == 'rseqiops':
                rseqiops = int(kv[1])
            elif kv[0] == 'rrandiops':
                rrandiops = int(kv[1])
            elif kv[0] == 'wbps':
                wbps = int(kv[1])
            elif kv[0] == 'wseqiops':
                wseqiops = int(kv[1])
            elif kv[0] == 'wrandiops':
                wrandiops = int(kv[1])       
        return IOCostModel(major_minor, ctrl, model, rbps, rseqiops, rrandiops, wbps, wseqiops, wrandiops)

@dataclass
class IOCostQOS:
    major_minor: str
    enable: bool
    ctrl: str 
    rpct: float
    rlat: int
    wpct: float
    wlat: int
    min: float
    max: float

    def to_str(self) -> str:
        return f"{self.major_minor} enable={'1' if self.enable else '0'} ctrl={self.ctrl} rpct={self.rpct} rlat={self.rlat} wpct={self.wpct} wlat={self.wlat} min={self.min} max={self.max}"

    @staticmethod
    def from_str(text: str):
        args = text.strip().split(" ")
        if len(args) == 1:
            return None
        major_minor = args[0]
        enable = False
        ctrl = "user"
        rpct = rlat = wpct = wlat = min = max = 0
        for arg in args[1:]:
            kv = arg.split("=")
            if kv[0] == 'enable':
                enable = True if kv[1] == "1" else False   
            elif kv[0] == 'ctrl':
                ctrl = kv[1]   
            elif kv[0] == 'rpct':
                rpct = float(kv[1])    
            elif kv[0] == 'rlat':
                rlat = int(kv[1])
            elif kv[0] == 'wpct':
                wpct = float(kv[1])
            elif kv[0] == 'wlat':
                wlat = int(kv[1])
            elif kv[0] == 'min':
                min = float(kv[1])
            elif kv[0] == 'max':
                max = float(kv[1])       
        return IOCostQOS(major_minor, enable, ctrl, rpct, rlat, wpct, wlat, min, max)

@dataclass
class IOWeight:
    major_minor: str
    weight: int | str

    def to_str(self) -> str:
        return f"{self.major_minor} {self.weight}"

    @staticmethod
    def from_str(text: str):
        args = text.strip().split(" ")
        return IOWeight(args[0], args[1])

class IOPriorityClass(Enum):
    NO_CHANGE="no-change"
    PROMOTE_TO_RT="promote-to-rt"
    RESTRICT_TO_BE="restrict-to-be"
    IDLE="idle"
    NONE_TO_RT="none-to-rt"
    UNKNOWN="unknown"

    @staticmethod
    def from_str(label: str):
        try:
            return  {
                'no-change': IOPriorityClass.NO_CHANGE,
                'promote-to-rt': IOPriorityClass.PROMOTE_TO_RT,
                'restrict-to-be': IOPriorityClass.RESTRICT_TO_BE,
                'idle': IOPriorityClass.IDLE,
                'none-to-rt': IOPriorityClass.NONE_TO_RT
            }[label]
        except:
            return IOPriorityClass.UNKNOWN

@dataclass
class IOLatency:
    major_minor: str
    target: int

    def to_str(self) -> str:
        return f"{self.major_minor} target={self.target}"

    @staticmethod
    def from_str(text: str):
        args = text.strip().split(" ")
        return IOLatency(args[0], int(args[1].split("=")[1].strip()))

class Cgroup(object):
    """wrapper for one control-group"""

    def __init__(self, cgroup_path: str):
        if not os.path.exists(cgroup_path) or cgroup_syspath not in cgroup_path:
            raise ValueError('invalid cgroup')
        self.cgroup_path = cgroup_path

    @property
    def iocontrol_enabled(self) -> bool:
        with open(f"{self.cgroup_path}/cgroup.subtree_control", "r") as f:
            return "io" in f.readline()

    @property
    def path(self) -> str:
        return self.cgroup_path

    @property
    def subpath(self) -> str:
        return self.path[len(cgroup_syspath):]

    @property
    def iomax(self) -> list[IOMax]:
        if not self.iocontrol_enabled:
            raise ValueError("iocontrol not enabled for this group")
        lines = []
        with open(f"{self.cgroup_path}/io.max", "r") as f:
            lines = f.readlines()
        return [IOMax.from_str(line) for line in lines]
        
    @iomax.setter
    def iomax(self, iomax_val: IOMax):
        if not self.iocontrol_enabled:
            raise ValueError("iocontrol not enabled for this group")
        set_sysfs(f"{self.cgroup_path}/io.max", iomax_val.to_str())    

    @iomax.deleter
    def iomax(self):
        if not self.iocontrol_enabled:
            return
        for iomax_val in self.iomax:
            iomax_val.rbps = iomax_val.wbps = iomax_val.riops = iomax_val.wiops = None
            self.iomax = iomax_val
    
    @property
    def ioweight(self) -> [IOWeight]:
        if not self.iocontrol_enabled:
            raise ValueError("iocontrol not enabled for this group")
        lines = []
        with open(f"{self.cgroup_path}/io.weight", "r") as f:
            lines = f.readlines()
        return [IOWeight.from_str(line) for line in lines]
        
    @ioweight.setter
    def ioweight(self, ioweight_val: IOWeight):
        if not self.iocontrol_enabled:
            raise ValueError("iocontrol not enabled for this group")
        if type(ioweight_val.weight) != str and (int(ioweight_val.weight) < 1 or int(ioweight_val.weight) > 10_000):
            raise ValueError("Invalid weight")
        set_sysfs(f"{self.cgroup_path}/io.weight", ioweight_val.to_str())    

    @ioweight.deleter
    def ioweight(self):
        if not self.iocontrol_enabled:
            return
        for ioweight_val in self.ioweight:
            if ioweight_val.major_minor == "default":
                continue
            ioweight_val.weight = "default"
            self.ioweight = ioweight_val

    @property
    def ioprio(self) -> IOPriorityClass:
        if not self.iocontrol_enabled:
            raise ValueError("iocontrol not enabled for this group")
        with open(f"{self.cgroup_path}/io.prio.class", "r") as f:
            return IOPriorityClass.from_str(f.readline().strip())
            
    @ioprio.setter
    def ioprio(self, prio: IOPriorityClass):
        if not self.iocontrol_enabled:
            raise ValueError("iocontrol not enabled for this group")
        set_sysfs(f"{self.cgroup_path}/io.prio.class", prio.value)

    @ioprio.deleter
    def ioprio(self):
        if not self.iocontrol_enabled:
            return
        self.ioprio = IOPriorityClass.NO_CHANGE        

    @property
    def iolatency(self) -> [IOLatency]:
        if not self.iocontrol_enabled:
            raise ValueError("iocontrol not enabled for this group")
        lines = []
        with open(f"{self.cgroup_path}/io.latency", "r") as f:
            lines = f.readlines()
        return [IOLatency.from_str(line) for line in lines]
        
    @iolatency.setter
    def iolatency(self, iolatency_val: IOLatency):
        if not self.iocontrol_enabled:
            raise ValueError("iocontrol not enabled for this group")
        set_sysfs(f"{self.cgroup_path}/io.latency", iolatency_val.to_str())    

    @iolatency.deleter
    def iolatency(self):
        if not self.iocontrol_enabled:
            return
        for iolatency_val in self.iolatency:
            iolatency_val.target = 0
            self.iolatency = iolatency_val

    def disable_iocontrol(self):
        del self.iomax
        del self.ioweight
        del self.ioprio
        del self.iolatency

def list_cgroups(path=cgroup_syspath):
    return [folder for folder, _, _ in os.walk(Path(path))][1:]

def create_cgroup(relative_path) -> Cgroup:
    cgroup_path = f"{cgroup_syspath}/{relative_path}"
    subprocess.check_call(f"sudo mkdir -m='0755' -p {cgroup_path}", shell=True)
    set_sysfs(f"{cgroup_path}/cgroup.subtree_control", "+io")
    return Cgroup(cgroup_path)

def set_iocost(model: IOCostModel, qos: IOCostQOS):
    set_sysfs(f"{cgroup_syspath}/io.cost.model", model.to_str())    
    set_sysfs(f"{cgroup_syspath}/io.cost.qos", qos.to_str())    

def get_iocost():
    model = None
    if os.path.exists(f"{cgroup_syspath}/io.cost.model"):  
        with open(f"{cgroup_syspath}/io.cost.model", "r") as f:
            model =  IOCostModel.from_str(f.readline()) 
    qos = None  
    with open(f"{cgroup_syspath}/io.cost.qos", "r") as f:
        qos =  IOCostQOS.from_str(f.readline()) 
    return (model, qos)

def disable_iocost():
    model, qos = get_iocost()
    if model is not None and qos is not None:
        qos.enable = False
        set_iocost(model, qos)


def disable_iocontrol():
    # Disable group control
    for group in [Cgroup(f"{spath}") for spath in list_cgroups(cgroup_syspath)[1:]]:
        group.disable_iocontrol()
    # Disable global control
    disable_iocost()
    