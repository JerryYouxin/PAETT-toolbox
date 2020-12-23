#!/bin/bash
set -e
BENCHMARKS="IS"

module load clang

for B in $BENCHMARKS
do
  echo Compiling original $B
  sh build-ori.sh $B
  echo Compiling instrumented $B
  sh build-inst.sh $B
done
