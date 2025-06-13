#!/bin/bash

# Test lat scalability of iocost
python3 prio.py --iocost=1 --tapps=1 --rq=1 --access=1 --rwshort=1 --numjobs=5
python3 prio.py --iocost=1 --tapps=1 --numjobs=17

# Test bandwidth scalability of iocost
python3 prio.py --iocost=1 --tapps_joined=1 --numjobs=17
python3 prio.py --iocost=1 --tapps_joined=1 --rq_joined=1 --access_joined=1 --rwshort_joined=1 --numjobs=5

# schedulers do not work
python3 prio.py --mq=1 --bfq2=1  --tapps_joined=1 --numjobs=5
python3 prio.py --mq=1 --bfq2=1  --tapps=1 --numjobs=5

# Test other knobs
python3 prio.py --iomax=1 --iolat=1 --tapps_joined=1 --rq_joined=1 --access_joined=1 --rwshort_joined=1 --numjobs=5
python3 prio.py --iomax=1 --iolat=1 --tapps=1 --rq=1 --access=1 --rwshort=1 --numjobs=5

# Test write
python3 prio.py --iocost=1 --rwlong_joined=1 --configpoint=0 --numjobs=5
python3 prio.py --iocost=1 --rwlong_joined=1 --configpoint=5 --numjobs=5
python3 prio.py --iocost=1 --rwlong_joined=1 --configpoint=15 --numjobs=5
python3 prio.py --iocost=1 --rwlong_joined=1 --configpoint=30 --numjobs=5
python3 prio.py --iocost=1 --rwlong_joined=1 --configpoint=45 --numjobs=5

python3 prio.py --iocost=1 --rwlong=1 --configpoint=0 --numjobs=5
python3 prio.py --iocost=1 --rwlong=1 --configpoint=5 --numjobs=5
python3 prio.py --iocost=1 --rwlong=1 --configpoint=15 --numjobs=5
python3 prio.py --iocost=1 --rwlong=1 --configpoint=30 --numjobs=5
python3 prio.py --iocost=1 --rwlong=1 --configpoint=45 --numjobs=5