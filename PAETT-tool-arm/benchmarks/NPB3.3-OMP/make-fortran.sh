#!/bin/bash
set -e

module () 
{ 
    eval `/usr/bin/modulecmd bash $*`
}

BENCHMARKS="BT CG EP FT LU MG SP UA"

module load flang

for B in $BENCHMARKS
do
  echo Compiling original $B
  sh build-ori.sh $B
  echo Compiling instrumented $B
  sh build-inst.sh $B
done
