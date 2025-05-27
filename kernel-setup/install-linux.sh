#!/bin/bash 

set -e

# Ensure dir
dir="$(cd -P -- "$(dirname -- "$0")" && pwd -P)"

# Clean builds
mkdir -P linux-build  
cd linux-build

# Git
git clone https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git linux-6.9-rc7
pushd linux-6.9-rc7
git checkout v6.9-rc7

# Compile
cp ../config-socc .config
scripts/config --disable SYSTEM_TRUSTED_KEYS
scripts/config --disable SYSTEM_REVOCATION_KEYS
scripts/config --disable DEBUG_INFO
scripts/config --enable BLK_CGROUP_IOLATENCY

make menuconfig
make -j 20 bindeb-pkg LOCALVERSION=-local
popd
