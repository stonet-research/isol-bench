import subprocess

def start_sar(out: str, core: str):
    cmd = f'sudo taskset -c {core} sudo sar -P {core} -u 1 60 2>&1 1>{out}'
    pidstat = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT)
    return pidstat

def start_sar_mem(out: str, core: str):
    cmd = f'sudo taskset -c {core} sudo sar -P {core} -r 1 60 2>&1 1>{out}'
    pidstat = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT)
    return pidstat

def kill_sar():
    cmd = f'sudo pkill -9 ^sar$'
    return subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT)

def parse_sar(filename: str, core: str):
    tmp = []
    with open(filename) as file:
        tmp = []
        for line in file:
            l = line.split()
            try:
                if l[2] == core:
                    v = float(l[3]) + float(l[5])
                    tmp.append(v)
            except:
                continue
    return tmp