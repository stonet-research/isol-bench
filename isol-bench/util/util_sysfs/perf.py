import subprocess

perf_bin = f"/home/user/bin/perf"

def perf_record(out: str, core: str, glob: bool, running_time: int):    
    cmd = f'sudo taskset -c {core} sudo {perf_bin} record -a -e cycles,instructions -F 99 --overwrite -o {out} {"-g" if glob else ""}'
    if running_time:
        cmd = f"{cmd} -- sleep {running_time}"
    subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT)

def perf_report(inf: str, out: str):
    cmd = f'sudo {perf_bin} report -n -m --stdio --full-source-path --source -s symbol -i {inf} > {out}'
    subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT)

def perf_stat(out: str, core: str, glob: bool, running_time: int):    
    cmd = f'sudo taskset -c {core} sudo {perf_bin} stat -a -e cycles,instructions,cache-misses,cache-references -r 1 -o {out} {"-a" if glob else ""}'
    if running_time:
        cmd = f"{cmd} -- sleep {running_time}"
    subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT)

def get_perf_cycles(filename: str):
    with open(filename) as file:
        for line in file:
            if 'cycles' in line:
                l = line.strip().split(' ')
                c = l[0].replace(",","")
                return int(c)
    return None