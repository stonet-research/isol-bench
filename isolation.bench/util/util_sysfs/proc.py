import subprocess
import sys

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

