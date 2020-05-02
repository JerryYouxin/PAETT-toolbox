#!/bin/bash
unzip llvm-project-release-9.x.zip
cp -r src llvm-project-release-9.x/llvm/lib/Transform/PAETT
cp -r include llvm-project-release-9.x/llvm/include/llvm/Transform/PAETT
cd llvm-project-release-9.x
sh make.sh