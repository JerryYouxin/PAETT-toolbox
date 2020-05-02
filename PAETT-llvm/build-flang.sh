#!/bin/bash
unzip flang-paett.zip
cp -r src flang-paett/llvm/lib/Transform/PAETT
cp -r include flang-paett/llvm/include/llvm/Transform/PAETT
cd flang-paett
sh ./build.sh