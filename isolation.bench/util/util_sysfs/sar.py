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
    tmp = [[] for i in range(256)]
    with open(filename) as file:
        for line in file:
            l = line.split()
            try:
                if "PM" in l[1] or "AM" in l[1]:
                    v = float(l[3]) + float(l[5])
                    tmp[int(l[2])].append(v)
            except:
                continue

    cores = core.split('0')
    x1 = int(core.split('-')[0])
    x2 = int(core.split('-')[1])+1 if len(cores) > 1 else x1+1
    
    y = []
    for i in range(0, len(tmp[x1])):
        o = 0
        for j in range(x1, x2):
            o = o + tmp[j][i]
        y.append(o)        
    return y