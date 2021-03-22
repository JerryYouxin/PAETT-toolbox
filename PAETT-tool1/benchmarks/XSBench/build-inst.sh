#!/bin/bash
set -e

module () 
{ 
    eval `/usr/bin/modulecmd bash $*`
}

module load clang
cd src
cp Makefile.inst Makefile
# first compilation for significant region detection
make clean
make -j4
mkdir -p detect/
# run for significant region detection
cd detect
export PAETT_DETECT_MODE=ENABLE
../XSBench
filter_gen --out paett.filt --prof_fn libpaett_inst.log
cd ..
# filter generated, now re-compile for profile instrumentation
export PAETT_CCT_FREQUENCY_COMMAND_FILTER=`pwd`/detect/paett.filt
make clean
make -j4
mv ./XSBench ./XSBench.inst
cd ..
