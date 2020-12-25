#!/bin/bash
set -e

module () 
{ 
    eval `/usr/bin/modulecmd bash $*`
}

RED='\033[1;31m'
GREEN='\033[1;32m'
NC='\033[0m' # No Color

module load flang

BENCHMARKS="BT CG EP FT LU MG SP UA"
for B in $BENCHMARKS
do
  echo -e ${GREEN}Collecting data for ${RED}${B}${NC}
  mkdir -p ../COLLECT/$B
  collect_data --keymap=detect/$B/PAETT.keymap --out=../COLLECT/$B/metric.out --exe=./bin/$B.C.inst --papi=PAPI_BR_NTK,PAPI_LD_INS,PAPI_L2_ICR,PAPI_BR_MSP,PAPI_RES_STL,PAPI_SR_INS,PAPI_L2_DCR --consistant
done

module rm flang

module load clang

BENCHMARKS="IS"
for B in $BENCHMARKS
do
  echo -e ${GREEN}Collecting data for ${RED}${B}${NC}
  mkdir -p ../COLLECT/$B
  collect_data --keymap=detect/$B/PAETT.keymap --out=../COLLECT/$B/metric.out --exe=./bin/$B.C.inst --papi=PAPI_BR_NTK,PAPI_LD_INS,PAPI_L2_ICR,PAPI_BR_MSP,PAPI_RES_STL,PAPI_SR_INS,PAPI_L2_DCR --consistant
done

module rm clang
