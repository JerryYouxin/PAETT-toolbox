#!/bin/bash
# collect data
cd NPB3.3-OMP
sh collect.sh
cd ..

cd XSBench
sh collect.sh
cd ..