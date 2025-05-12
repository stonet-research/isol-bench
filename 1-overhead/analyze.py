import json

def avg(ar):
    return sum(ar) / len(ar)


for knob in [\
    "baremetal-none", "baremetal-priomq", "baremetal-priobfq", \
    "max", \
    "none", "priomq", "priobfq", \
    "iolat", "iocost", \
    "priomq-256"\
    ]:
    print('------------')
    print(knob)
    print('------------')
    with open(f"out/{knob}-sar") as file:
        usr = []
        sys = []
        for line in file:
            l = line.split()
            try:
                usr.append(float(l[3]))
                sys.append(float(l[5]))
            except:
                continue

        n = "sar"
        print(f'{n} usr', avg(usr))
        print(f'{n} sys', avg(sys))
        print(f'{n} sum', avg(usr) + avg(sys))

    with open(f"out/{knob}-pidstat") as file:
        usr = []
        sys = []

        tmpusr = []
        tmpsys = []
        for line in file:
            l = line.split()
            if 'CPU  Command' in line and len(tmpusr):
                usr.append(sum(tmpusr))
                sys.append(sum(tmpsys))
                tmpusr = []
                tmpsys = []
            if len(l) > 2 and '-' in l[3]:
                continue 
            try:
                tmpusr.append(float(l[5]))
                tmpsys.append(float(l[6]))
            except:
                continue
        if len(tmpusr):
            usr.append(sum(tmpusr))
            sys.append(sum(tmpsys))

        n = "pidstat"
        print(f'{n} usr', avg(usr))
        print(f'{n} sys', avg(sys))
        print(f'{n} sum', avg(usr) + avg(sys))

    with open(f"out/{knob}.json") as file:
        for line in file:
            if 'usr_cpu' in line:
                usr=[float(line.split()[2][:-1])]
            if 'sys_cpu' in line:
                sys=[float(line.split()[2][:-1])]
        n = "fio"
        print(f'{n} usr', avg(usr))
        print(f'{n} sys', avg(sys))
        print(f'{n} sum', avg(usr) + avg(sys))


for knob in [('baremetal-', 'raw-'), ('docker-', 'docker-'), ('cgroups-', 'cgroups-')]:
    lpid = []
    tails = []
    for j in [2**i for i in range(0,9)]:
        
        # pidstat
        lpidtemp = []
        with open(f"out/{knob[0]}priomq-{j}-intra-{knob[1]}pidstat") as file:
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


        # json
        with open(f"out/{knob[0]}priomq-{j}-intra-{knob[1]}"[:-1] + f".json") as file:
            data = json.load(file)
            tail = list(data['jobs'][0]['read']['clat_ns']['percentile'].values())
            tails.append(tail)

    print(knob[0])
    print('cpu', lpid)
    print('t', [t[-5] for t in tails])