#!/bin/bash

eui64=$(sudo nvme id-ns $1 -o=json | jq -r '.eui64')
mkdir -p tmp
echo ${eui64} > tmp/testdrive
echo ${eui64} 

