#!/bin/bash
unzip flang-paett.zip
cp -r src flang-paett/llvm/lib/Transforms/PAETT
cp -r include flang-paett/llvm/include/llvm/Transforms/PAETT
cd flang-paett
sh ./build.sh