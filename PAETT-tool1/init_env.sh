#!/bin/bash
set -e
NUM=28

for (( i=0; i<$NUM; i=i+1 ))
do
  echo 2400000 > /sys/devices/system/cpu/cpu$i/cpufreq/scaling_min_freq
  echo userspace > /sys/devices/system/cpu/cpu$i/cpufreq/scaling_governor
done
