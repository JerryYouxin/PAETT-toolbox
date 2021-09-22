#!/bin/bash
set -e

module () 
{ 
    eval `/usr/bin/modulecmd bash $*`
}

RED='\033[1;31m'
GREEN='\033[1;32m'
NC='\033[0m' # No Color

cd src
module load clang

echo -e ${GREEN}Collecting data for ${RED}XSBench${NC}
mkdir -p ../../COLLECT-$1/XSBench
chmod +x run-inst.sh
collect_data --keymap=detect/PAETT.keymap --out=../../COLLECT/XSBench/metric.out --exe=./run-inst.sh --papi=PAPI_BR_NTK,PAPI_LD_INS,PAPI_L2_ICR,PAPI_BR_MSP,PAPI_RES_STL,PAPI_SR_INS,PAPI_L2_DCR --consistant --target=$1

module rm clang
cd ..