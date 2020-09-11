#!/bin/bash
#unzip llvm-project-release-9.x.zip
mkdir llvm-project-release-9.x/llvm/lib/Transforms/PAETT
mkdir llvm-project-release-9.x/llvm/include/llvm/Transforms/PAETT
cp -r src/* llvm-project-release-9.x/llvm/lib/Transforms/PAETT/
cp -r include/* llvm-project-release-9.x/llvm/include/llvm/Transforms/PAETT/
cd llvm-project-release-9.x
sh make.sh
