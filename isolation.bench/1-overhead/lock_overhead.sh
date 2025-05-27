#!/bin/bash 
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

PERF_CMD="$(which perf)"
VMLINUX="/boot/vmlinuz-$(uname -r)"
DEV="/dev/nvme0n1"

mkdir -p out

fio_workload=$(cat <<EOF
    --name=locked \
    \
    --rw=randread \
    --filename=${DEV} \
    --time_based=1 \
    --runtime=10s \
    \
    --direct=1 \
    --bs=4096 \
    --ioengine=io_uring \
    --registerfiles=1 \
    --fixedbufs=1 
EOF
)

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

enable_max() {
    major_minor=$1
    cgroup=$2

    echo "${major_minor}  rbps=10000000000 wbps=10000000000 riops=10000000000 wiops=10000000000" |\
        sudo tee /sys/fs/cgroup/${cgroup}/io.max
}

# Setup cgroups
create_cgroups 16
DEVNUM=$(get_dev_num ${DEV})
echo "Using device ${DEVNUM}"

options=(baremetal none max priomq priobfq iolat iocost)
options=(max)

# CPU

# PERF
for option in ${options[@]}; do 
    case ${option} in  
        max)
            enable_max "${DEVNUM}" "workload-0.slice"
            ;;
        *)
            ;;
    esac 

    # Start perf process
    sudo "${PERF_CMD}" record \
            -a \
            -e cycles,instructions \
            -F 99  \
            -g -- \
                fio \
                    --numjobs=1 \
                    --iodepth=1 \
                    ${fio_workload} 

    # Report
    sudo "${PERF_CMD}" report \
        -n \
        -m \
        --stdio \
        --full-source-path \
        --source \
    -   -s symbol \
            > out/record-${option}

    # cleanup
    rm -rf perf.data perf.data.old
done 


#     lock_symbol = [
#     'native_queued_spin_lock_slowpath', '_raw_spin_lock', '_raw_spin_lock_irq',
#     '_raw_spin_unlock_irq', '_raw_spin_lock_irqsave', '_raw_spin_unlock',
#     'mutex_lock', 'mutex_unlock'
# ]