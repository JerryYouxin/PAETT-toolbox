#!/bin/bash
set -e
cp config/make.def.inst config/make.def
# first compilation for significant region detection
cd $1
make clean
cd ..
make CLASS=C $1
lower=`echo "$1" | tr '[:upper:]' '[:lower:]'`
mkdir -p detect/$1
mv bin/${lower}.C.x detect/$1/$1.C.inst
# run for significant region detection
cd detect/$1
export PAETT_DETECT_MODE=ENABLE
./$1.C.inst
filter_gen --out paett.filt --prof_fn libpaett_inst.log
cd ../../
# filter generated, now re-compile for profile instrumentation
export PAETTPAETT_CCT_FREQUENCY_COMMAND_FILTER=`pwd`/detect/$1/paett.filt
cd $1
make clean
cd ..
make CLASS=C $1
mv bin/${lower}.C.x bin/$1.C.inst
