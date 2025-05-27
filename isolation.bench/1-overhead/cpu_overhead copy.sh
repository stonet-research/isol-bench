#!/bin/bash 
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

PERF_CMD="$(which perf)"
VMLINUX="/boot/vmlinuz-$(uname -r)"
DEV="nvme0n1"

mkdir -p out
sudo chown user:user "/dev/${DEV}"


get_dev_num() {
    nvme_drive=$1
    nvme_drive_minor=$(echo "ibase=16; $(stat -c '%T' ${nvme_drive})"  | bc)
    nvme_drive_major=$(echo "ibase=16; $(stat -c '%t' ${nvme_drive})"  | bc)
    nvme_drive_major_minor="${nvme_drive_major}:${nvme_drive_minor}"
    echo "${nvme_drive_major_minor}"
}

create_cgroups() {
    for i in $(seq 0 $1); do
        if ! [ -f /sys/fs/cgroup/workload-${i}.slice ]; then
            sudo mkdir -p /sys/fs/cgroup/workload-${i}.slice
        fi
    done 
}

disable_max() {
    DEVNUM=$(get_dev_num "/dev/${1}")
    major_minor=${DEVNUM}
    cgroup=$2

    echo "${major_minor}  rbps=max wbps=max riops=max wiops=max" |\
        sudo tee /sys/fs/cgroup/${cgroup}/io.max > /dev/null
}

enable_max() {
    DEVNUM=$(get_dev_num "/dev/${1}")
    major_minor=${DEVNUM}
    cgroup=$2

    echo "${major_minor}  rbps=10000000000 wbps=10000000000 riops=10000000 wiops=10000000" |\
        sudo tee /sys/fs/cgroup/${cgroup}/io.max > /dev/null
}

set_scheduler() {
    sudo modprobe bfq > /dev/null
    echo ${2} | sudo tee /sys/block/${1}/queue/scheduler > /dev/null
}

set_iolat() {
    DEVNUM=$(get_dev_num "/dev/${1}")
    major_minor=${DEVNUM}
    cgroup=$2

    echo "${major_minor}  target=100000" |\
        sudo tee /sys/fs/cgroup/${cgroup}/io.latency > /dev/null
}

unset_iolat() {
    DEVNUM=$(get_dev_num "/dev/${1}")
    major_minor=${DEVNUM}
    cgroup=$2

    echo "${major_minor}  target=0" |\
        sudo tee /sys/fs/cgroup/${cgroup}/io.latency > /dev/null
}


set_iocost() {
    DEVNUM=$(get_dev_num "/dev/${1}")
    major_minor=${DEVNUM}
    cgroup=$2

    echo "${major_minor} enable=1 ctrl=user rpct=95.00 rlat=100000 wpct=95.00 wlat=100000 min=50.00 max=150.00" |\
        sudo tee /sys/fs/cgroup/io.cost.qos > /dev/null
    echo "${major_minor} ctrl=user model=linear rbps=10000000000 rseqiops=10000000 rrandiops=10000000 wbps=10000000000 wseqiops=10000000 wrandiops=10000000" |\
        sudo tee /sys/fs/cgroup/io.cost.model > /dev/null
}

unset_iocost() {
    DEVNUM=$(get_dev_num "/dev/${1}")
    major_minor=${DEVNUM}
    cgroup=$2

    echo "${major_minor} enable=0" |\
        sudo tee /sys/fs/cgroup/io.cost.qos > /dev/null
}

disable_all() {
    disable_max ${1} ${2}
    set_scheduler ${1} "none" 
    unset_iolat ${1} ${2}
    unset_iocost ${1} ${2}
}

start_fio() {
    fiop="$1"
    cores=$2
    dev=$3
    file=$4

    sudo ${fiop} \
        --filename=${dev} \
        --output-format=json \
        --output=${file} \
        --cpus_allowed=${cores} \
        ${SCRIPT_DIR}/jobs/randread.fio &
    pid=$!
    sleep 1
    fiopids=$(pgrep ^fio  | paste -sd,)
    
    # CPU measurement
    sudo taskset -c 1 sudo pidstat -p ${fiopids} -t 1 -u 2>&1 1>out/${option}-pidstat &
    sudo taskset -c 1 sudo sar -P ${cores} -u 1 60 2>&1 1>out/${option}-sar &   
    sarpid=$!
    wait ${pid}
    sudo kill -9 ${sarpid} 2>&1 1>/dev/null
    
    return
}


start_fio_docker() {
    fiop="$1"
    cores=$2
    dev=$3
    file=$4
    cgc=$5

    # for numjobs in 1 2 4 8 16 32 64 128 256; do
    # for numjobs in 1 256; do
    #     docker container prune -f
    #     truefile=${file}-${numjobs}-intra.json
    #     sudo touch ${truefile}
    #     docker run \
    #         --name=runfio \
    #         --cgroup-parent="workload-0.slice" \
    #         --cpuset-cpus ${cores} \
    #         --device ${dev}:"/var/lib/nvme" \
    #         -v "${truefile}":"${truefile}" \
    #         -v "${SCRIPT_DIR}/jobs/randread.fio":"${SCRIPT_DIR}/jobs/randread.fio" \
    #         --security-opt seccomp=unconfined \
    #         "fio" \
    #             --filename="/var/lib/nvme" \
    #             --output-format=json \
    #             --output=${truefile} \
    #             --cpus_allowed=${cores} \
    #             --numjobs=${numjobs} \
    #             --thread=0 \
    #             --group_reporting=1 \
    #             ${SCRIPT_DIR}/jobs/randread.fio &
    #     sleep 10
    #     fiopids=$(pgrep ^fio  | paste -sd,)
        
    #     # CPU measurement
    #     sudo taskset -c 1 sudo pidstat -p ${fiopids} -t 1 -u 2>&1 1>out/${option}-${numjobs}-intra-pidstat &
    #     sudo taskset -c 1 sudo sar -P ${cores} -u 1 60 2>&1 1>out/${option}-${numjobs}-intra-sar &   
    #     sarpid=$!
    #     docker wait runfio
    #     sudo kill -9 ${sarpid} 2>&1 1>/dev/null
    # done


    for containers in 256; do
        docker container prune -f
        for c in $(seq 1 ${containers}); do 
            truefile=${file}-${containers}-of-${c}-inter.json
            sudo touch ${truefile}
            # docker run \
            #     --name=runfio-${c} \
            #     --cgroup-parent="workload-${c}.slice" \
            #     --cpuset-cpus ${cores} \
            #     --device ${dev}:"/var/lib/nvme" \
            #     -v "${truefile}":"${truefile}" \
            #     -v "${SCRIPT_DIR}/jobs/randread.fio":"${SCRIPT_DIR}/jobs/randread.fio" \
            #     --security-opt seccomp=unconfined \
            #     "fio" \
            #         --filename="/var/lib/nvme" \
            #         --output-format=json \
            #         --output=${truefile} \
            #         --cpus_allowed=${cores} \
            #         --numjobs=1 \
            #         --thread=0 \
            #         --group_reporting=1 \
            #         ${SCRIPT_DIR}/jobs/randread.fio &

            sudo fio \
                --filename=${dev} \
                --output-format=json \
                --cpus_allowed=${cores} \
                ${SCRIPT_DIR}/jobs/randread.fio &
        done
        sleep 10
        fiopids=$(pgrep ^fio  | paste -sd,)
        
        # CPU measurement
        sudo taskset -c 1 sudo pidstat -p ${fiopids} -t 1 -u 2>&1 1>out/${option}-${numjobs}-inter-pidstat &
        sudo taskset -c 1 sudo sar -P ${cores} -u 1 60 2>&1 1>out/${option}-${numjobs}-inter-sar &   
        sarpid=$!
        for c in $(seq 1 ${containers}); do 
            docker wait runfio-${c}
        done
        sudo kill -9 ${sarpid} 2>&1 1>/dev/null
    done

    return
}

# Setup cgroups
cgroup_count=256
create_cgroups ${cgroup_count}

options=(baremetal-none baremetal-priomq baremetal-priobfq max none priomq priobfq iolat iocost)
options=(priomq)

# CPU
for option in ${options[@]}; do
    for c in $(seq 0 ${cgroup_count}); do 
        disable_all "${DEV}" "workload-${c}.slice"
        case ${option} in  
            *none*)
                ;;
            max)
                enable_max "${DEV}" "workload-${c}.slice"
                ;;
            *priomq*)
                set_scheduler "${DEV}" "mq-deadline"
                ;;
            *priobfq*)
                set_scheduler "${DEV}" "bfq"
                ;;
            iolat)
                set_iolat "${DEV}" "workload-${c}.slice"
                ;;
            iocost)
                set_iocost "${DEV}"  "workload-${c}.slice"
                ;;
            *)
                ;;
        esac 
    done

    FIO='../fio/fio'
    CORES='5'

    case ${option} in  
        bare*)
            start_fio ${FIO} ${CORES} "/dev/${DEV}" ${SCRIPT_DIR}/out/${option} 
            ;;
        *)
            start_fio_docker ${FIO} ${CORES} "/dev/${DEV}" ${SCRIPT_DIR}/out/${option} ${cgroup_count}
            ;;
    esac
done 

for c in $(seq 0 ${cgroup_count}); do 
    disable_all "${DEV}" "workload-${c}.slice"
done
reset
