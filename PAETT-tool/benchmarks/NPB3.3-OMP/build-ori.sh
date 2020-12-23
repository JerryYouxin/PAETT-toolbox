#!/bin/bash
set -e
cp config/make.def.llvm config/make.def
make CLASS=C $1 clean
make CLASS=C $1
lower=`echo "$1" | tr '[:upper:]' '[:lower:]'`
mv bin/${lower}.C.x bin/$1.C.ori
