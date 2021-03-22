#!/bin/bash
chmod a+x sys/print_header
mkdir -p bin
sh make-fortran.sh
sh make-c.sh
