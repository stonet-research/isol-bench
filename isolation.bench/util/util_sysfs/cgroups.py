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

@dataclass
class IOBFQWeight:
    major_minor: str
    weight: int | str

    def to_str(self) -> str:
        return f"{self.major_minor} {self.weight}"

    @staticmethod
    def from_str(text: str):
        args = text.strip().split(" ")
        return IOBFQWeight(args[0], args[1])

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
            raise ValueError(f'invalid cgroup: {cgroup_path}')
        self.cgroup_path = cgroup_path

    @property
    def path(self) -> str:
        return self.cgroup_path

    @property
    def subpath(self) -> str:
        return self.path[len(cgroup_syspath):]

    @property
    def isroot(self) -> bool:
        return self.path == cgroup_syspath

    @property
    def parent(self):
        if self.isroot:
            return None
        parent_path = str(Path(self.path).parent.absolute())
        cgroup_parent = Cgroup(parent_path)
        return cgroup_parent

    @property
    def iocontrol_enabled(self) -> bool:
        with open(f"{self.cgroup_path}/cgroup.controllers", "r") as f:
            return "io" in f.readline()

    @iocontrol_enabled.setter
    def iocontrol_enabled(self, enabled_val: bool):
        set_sysfs(f"{self.cgroup_path}/cgroup.subtree_control", "+io" if enabled_val else "-io")    

    def force_cpuset_cpus(self, cpu: str):
        set_sysfs(f"{self.cgroup_path}/cpuset.cpus", cpu)    

    @property
    def iomax(self) -> list[IOMax]:
        if self.isroot or not self.parent.iocontrol_enabled:
            raise ValueError("iocontrol not available for this group")
        lines = []
        with open(f"{self.cgroup_path}/io.max", "r") as f:
            lines = f.readlines()
        return [IOMax.from_str(line) for line in lines]
        
    @iomax.setter
    def iomax(self, iomax_val: IOMax):
        if self.isroot or not self.parent.iocontrol_enabled:
            raise ValueError("iocontrol not available for this group")
        set_sysfs(f"{self.cgroup_path}/io.max", iomax_val.to_str())    

    @iomax.deleter
    def iomax(self):
        if self.isroot or not self.parent.iocontrol_enabled:
            return
        for iomax_val in self.iomax:
            iomax_val.rbps = iomax_val.wbps = iomax_val.riops = iomax_val.wiops = None
            self.iomax = iomax_val
    
    @property
    def ioweight(self) -> [IOWeight]:
        if self.isroot or not self.parent.iocontrol_enabled:
            raise ValueError("iocontrol not available for this group")
        lines = []
        with open(f"{self.cgroup_path}/io.weight", "r") as f:
            lines = f.readlines()
        return [IOWeight.from_str(line) for line in lines]
        
    @ioweight.setter
    def ioweight(self, ioweight_val: IOWeight):
        if self.isroot or not self.parent.iocontrol_enabled:
            raise ValueError("iocontrol not available for this group")
        if type(ioweight_val.weight) != str and (int(ioweight_val.weight) < 1 or int(ioweight_val.weight) > 10_000):
            raise ValueError(f"Invalid weight {ioweight_val.to_str()}")
        set_sysfs(f"{self.cgroup_path}/io.weight", ioweight_val.to_str())    

    @ioweight.deleter
    def ioweight(self):
        if self.isroot or not self.parent.iocontrol_enabled:
            return
        for ioweight_val in self.ioweight:
            ioweight_val.weight = "100"
            self.ioweight = ioweight_val

    @property
    def iobfqweight(self) -> [IOBFQWeight]:
        if self.isroot or not self.parent.iocontrol_enabled:
            raise ValueError("iocontrol not available for this group")
        lines = []
        with open(f"{self.cgroup_path}/io.bfq.weight", "r") as f:
            lines = f.readlines()
        return [IOBFQWeight.from_str(line) for line in lines]
        
    @iobfqweight.setter
    def iobfqweight(self, iobfqweight_val: IOBFQWeight):
        if self.isroot or not self.parent.iocontrol_enabled:
            raise ValueError("iocontrol not available for this group")
        if type(iobfqweight_val.weight) != str and (int(iobfqweight_val.weight) < 1 or int(iobfqweight_val.weight) > 1_000):
            raise ValueError(f"Invalid weight {iobfqweight_val.to_str()}")
        set_sysfs(f"{self.cgroup_path}/io.bfq.weight", iobfqweight_val.to_str())    

    @iobfqweight.deleter
    def iobfqweight(self):
        if self.isroot or not self.parent.iocontrol_enabled:
            return
        for iobfqweight_val in self.iobfqweight:
            iobfqweight_val.weight = "100"
            self.iobfqweight = iobfqweight_val

    @property
    def ioprio(self) -> IOPriorityClass:
        if self.isroot or not self.parent.iocontrol_enabled:
            raise ValueError("iocontrol not available for this group")
        with open(f"{self.cgroup_path}/io.prio.class", "r") as f:
            return IOPriorityClass.from_str(f.readline().strip())
            
    @ioprio.setter
    def ioprio(self, prio: IOPriorityClass):
        if self.isroot or not self.parent.iocontrol_enabled:
            raise ValueError("iocontrol not available for this group")
        set_sysfs(f"{self.cgroup_path}/io.prio.class", prio.value)

    @ioprio.deleter
    def ioprio(self):
        if self.isroot or not self.parent.iocontrol_enabled:
            return 
        self.ioprio = IOPriorityClass.NO_CHANGE        

    @property
    def iolatency(self) -> [IOLatency]:
        if self.isroot or not self.parent.iocontrol_enabled:
            raise ValueError("iocontrol not available for this group")
        lines = []
        with open(f"{self.cgroup_path}/io.latency", "r") as f:
            lines = f.readlines()
        return [IOLatency.from_str(line) for line in lines]
        
    @iolatency.setter
    def iolatency(self, iolatency_val: IOLatency):
        if self.isroot or not self.parent.iocontrol_enabled:
            raise ValueError("iocontrol not available for this group")
        set_sysfs(f"{self.cgroup_path}/io.latency", iolatency_val.to_str())    

    @iolatency.deleter
    def iolatency(self):
        if self.isroot or not self.parent.iocontrol_enabled:
            return 
        for iolatency_val in self.iolatency:
            iolatency_val.target = 0
            self.iolatency = iolatency_val

    def disable_iocontrol(self):
        if self.isroot:
            return
        del self.iomax
        del self.ioweight
        del self.iobfqweight
        del self.ioprio
        del self.iolatency

def list_cgroups(path=cgroup_syspath):
    return [folder for folder, _, _ in os.walk(Path(path))][1:]

def create_cgroup(relative_path, iocontrol_enabled=True) -> Cgroup:
    cgroup_path = f"{cgroup_syspath}/{relative_path}"
    subprocess.check_call(f"sudo mkdir -m='0755' -p {cgroup_path}", shell=True)
    cgroup = Cgroup(cgroup_path)
    cgroup.iocontrol_enabled = iocontrol_enabled
    return Cgroup(cgroup_path)

def create_cgroup_service(relative_path) -> Cgroup:
    cgroup = create_cgroup(relative_path, False)
    # Indeed, prio.class is not inherited, but we want it to be... Force it.
    cgroup_parent = Cgroup(str(Path(cgroup.path).parent.absolute()))
    cgroup.ioprio = cgroup_parent.ioprio
    return cgroup

def set_iocost(model: IOCostModel, qos: IOCostQOS):
    set_sysfs(f"{cgroup_syspath}/io.cost.model", model.to_str())    
    set_sysfs(f"{cgroup_syspath}/io.cost.qos", qos.to_str())    

def get_iocost():
    model = []
    if os.path.exists(f"{cgroup_syspath}/io.cost.model"):  
        with open(f"{cgroup_syspath}/io.cost.model", "r") as f:
            for line in f.readlines():
                model.append(IOCostModel.from_str(line)) 
    qos = []  
    with open(f"{cgroup_syspath}/io.cost.qos", "r") as f:
        for line in f.readlines():
            qos.append(IOCostQOS.from_str(line)) 

    out = []
    for q in qos:
        found = False
        for m in model:
            if q and m and q.major_minor == m.major_minor:
                out.append((m, q))
                found = True
        if not found:
            out.append((None, q))
    return out

def disable_iocost():
    for model, qos in get_iocost(): 
        if model is not None and qos is not None:
            qos.enable = False
            set_iocost(model, qos)

def disable_iocontrol_with_groups(groups: list[Cgroup]):
    for group in groups:
        group.disable_iocontrol()
    disable_iocost()

def disable_iocontrol(path = cgroup_syspath):
    disable_iocontrol_with_groups(
        [Cgroup(f"{spath}") for spath in list_cgroups(path)]
    )

def get_iocostmodel_from_nvme_model(nvme_device, unreachable = False):
    model = None
    amplifier = 10 if unreachable else 1
    if "Samsung SSD 980 PRO" in nvme_device.model:
        model = cgroups.IOCostModel(nvme_device.major_minor, 'user', 'linear', 2706339840 * amplifier, 786432 * amplifier, 786432 * amplifier, 1063126016 * amplifier, 135560 * amplifier, 130734 * amplifier)
    elif "INTEL SSDPE21D280GA" in nvme_device.model:
        model = cgroups.IOCostModel(nvme_device.major_minor, 'user', 'linear', 2413821952 * amplifier, 589312 * amplifier, 589312 * amplifier, 2413821952 * amplifier, 589312 * amplifier, 589312 * amplifier)
    else:
        raise ValueError("Model is not known, please add your own")
    return model