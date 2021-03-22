#!/bin/bash
# build for instrumentation
cd NPB3.3-OMP
sh make.sh
cd ..

cd XSBench
sh make.sh
cd ..