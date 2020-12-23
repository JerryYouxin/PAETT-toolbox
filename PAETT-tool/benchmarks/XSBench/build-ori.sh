#!/bin/bash
set -e
module load clang
pushd src
cp Makefile.llvm Makefile
make clean
make -j4
mv ./XSBench ./XSBench.ori
popd
