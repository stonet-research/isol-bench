#!/bin/bash

set -e

# Ensure dir
dir="$(cd -P -- "$(dirname -- "$0")" && pwd -P)"

cd ../../dependencies/fio
./configure
make -j
