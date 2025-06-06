import subprocess

def start_pidstat(out: str, core: str):    
    cmd = f'sudo taskset -c {core} sudo pidstat -p $(sudo pgrep ^fio | paste -sd,) -t 1 -u 2>&1 1>{out}'
    pidstat = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT)
    return pidstat

def kill_pidstat():
    cmd = f'sudo pkill -9 ^pidstat$'
    return subprocess.check_call(cmd, shell=True, stderr=subprocess.STDOUT)

def parse_pidstat(filename: str):
    lpidtemp = []
    with open(filename) as file:
        usr = []
        sys = []

        tmp = []
        for line in file:
            l = line.split()
            if 'CPU  Command' in line and len(tmp):
                lpidtemp.append(sum(tmp))
                tmp = []
            if len(l) > 2 and '-' in l[3]:
                continue 
            try:
                tmp.append(float(l[5]) + float(l[6]))
            except:
                continue
        if len(tmp):
            lpidtemp.append(sum(tmp))
    return lpidtemp    

