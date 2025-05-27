import json

def avg(ar):
    return sum(ar) / len(ar)

settings = [('baremetal-', 'raw-'), ('docker-', 'docker-'), ('cgroups-', 'cgroups-')]
knobs = ['none', 'priomq', 'priobfq'] + ['max', 'iolat', 'iocost']

for scaling in {"intra", "inter"}:
    for knob in knobs:
        for setting in settings:
            lpid = []
            sar = []
            tails = []
            fiocpus = []
            try:
                for j in [2**i for i in range(0,8)]:
                                        # pidstat
                    lpidtemp = []
                    f = f"out/{setting[0]}{knob}-{j}-{scaling}-{setting[1]}pidstat"
                    with open(f) as file:
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
                    lpidtemp = lpidtemp[:29]
                    lpid.append(avg(lpidtemp))

                    # Sar
                    f = f"out/{setting[0]}{knob}-{j}-{scaling}-{setting[1]}sar"
                    with open(f) as file:
                        usr = []
                        sys = []

                        tmp = []
                        for line in file:
                            l = line.split()
                            try:
                                tmp.append(float(l[3]) + float(l[5]))
                            except:
                                continue    
                    sar.append(avg(tmp))

                    # json
                    if scaling == "intra":
                        with open(f"out/{setting[0]}{knob}-{j}-{scaling}-{setting[1]}"[:-1] + f".json") as file:
                            data = json.load(file)
                            tail = list(data['jobs'][0]['read']['clat_ns']['percentile'].values())
                            tails.append(tail)
                            cpu = (data['jobs'][0]['usr_cpu'] + data['jobs'][0]['sys_cpu']) * j
                            fiocpus.append(cpu)
                    else:
                        f = f"out/{setting[0]}{knob}-{j}-of-1-{setting[1]}"[:-1] + f"-{scaling}.json"
                        with open(f) as file:
                            data = json.load(file)
                            tail = list(data['jobs'][0]['read']['clat_ns']['percentile'].values())
                            tails.append(tail)
                        cpu = 0
                        for i in range(1, j+1):
                            f = f"out/{setting[0]}{knob}-{j}-of-{i}-{setting[1]}"[:-1] + f"-{scaling}.json"
                            with open(f) as file:
                                data = json.load(file)     
                                cpu = cpu + data['jobs'][0]['usr_cpu'] + data['jobs'][0]['sys_cpu']
                        fiocpus.append(cpu)

                print(f"{setting[0]}-{scaling}-{knob}")
                print("---")
                print(f'cpu-{scaling}-{knob}', lpid, fiocpus, sar)
                print(f't-{scaling}-{knob}', [t[-5] for t in tails])
                print("---")
            except:
                continue
