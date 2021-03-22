if [ ! -n "$1" ]; then
    ./XSBench.inst
else
    ./XSBench.inst -t $1
fi
