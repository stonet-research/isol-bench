#!/bin/bash

set -e

# Ensure dir
dir="$(cd -P -- "$(dirname -- "$0")" && pwd -P)"

docker build --tag "iiswc-fio" .

