#!/bin/bash
# collect data
cd NPB3.3-OMP
sh collect.sh energy
cd ..

cd XSBench
sh collect.sh energy
cd ..