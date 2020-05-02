CXX=g++
CC=gcc

CFLAGS=-m64 -fopenmp -O3 -g -fpic -I../include -fpermissive
CXXFLAGS=-m64 -fopenmp -O3 -g -fpic -std=c++11 -I../include -fpermissive
LDFLAGS=-fopenmp -O3 -g

LIBFOLD=../lib

all:config.h libpaett_freqmod.so libcollect_energy.so libpaett_inst.so

%.c.o:%.c
	$(CC) $(CFLAGS) -c $< -o $@

%.cpp.o:%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

config.h: libpaett_freqmod.so config_gen
	./config_gen

config_gen: config_gen.cpp.o
	$(CXX) $(LDFLAGS) $(LIBFOLD)/libpaett_freqmod.so -lx86_energy $^ -o $@

libpaett_freqmod.so:libpaett_freqmod.cpp.o CallingContextTree.cpp.o
	$(CXX) $(LDFLAGS) -shared $^ -o $(LIBFOLD)/$@

libpaett_inst.so:libpaett_inst.cpp.o CallingContextTree.cpp.o
	$(CXX) $(LDFLAGS) -shared $^ -o $(LIBFOLD)/$@

libcollect_energy.so:libcollect_energy.cpp.o CallingContextTree.cpp.o
	$(CXX) $(LDFLAGS) -shared $^ -o $(LIBFOLD)/$@

clean:
	rm -rf *.o 