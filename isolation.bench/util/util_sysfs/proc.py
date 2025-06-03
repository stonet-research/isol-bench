import subprocess
import sys
import time

def check_kernel_requirements() -> bool:
    kernel = subprocess.check_output('uname -r 2>&1', shell=True, stderr=subprocess.STDOUT).decode(sys.stdout.encoding).strip()
    kernel_file = f'/boot/config-{kernel}'

    iolat_available = False
    with open(kernel_file, "r") as file:
        for line in file:
            occurence = line.find('CONFIG_BLK_CGROUP_IOLATENCY=y')
            comment = line.find('#')
            if occurence >= 0 and (comment < 0 or comment > occurence):
                iolat_available = True
                break 
    return iolat_available 


def exec_cmd(cmd, sudo=True):
    final_cmd = f'{"sudo" if sudo else ""} {cmd}'
    return subprocess.check_output(final_cmd, shell=True, stderr=subprocess.STDOUT)

def set_sysfs(path, value):
    subprocess.check_call(f"echo {value} | sudo tee {path} > /dev/null", shell=True)

def be_human():
    time.sleep(10)

def start_pidstat(out: str, core: str):    
    cmd = f'sudo taskset -c {core} sudo pidstat -p $(sudo pgrep ^fio | paste -sd,) -t 1 -u 2>&1 1>{out}'
    pidstat = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT)
    return pidstat

def start_sar(out: str, core: str):
    cmd = f'sudo taskset -c {core} sudo sar -P {core} -u 1 60 2>&1 1>{out}'
    pidstat = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT)
    return pidstat

def kill_sar():
    cmd = f'sudo pkill -9 ^sar$'
    pidstat = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT)
    return pidstat



