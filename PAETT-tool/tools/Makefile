all: freqcomm_gen paett_read_profile filter_significant_profile

CXX=g++
CC=gcc

CFLAGS=-m64 -fopenmp -O3 -g -I../include
CXXFLAGS=-m64 -fopenmp -O3 -g -std=c++11 -I../include
LDFLAGS=-m64 -fopenmp -O3 -g -L../lib/
BINFOLD=../bin

%.c.o:%.c
	$(CC) $(CFLAGS) -c $< -o $@

%.cpp.o:%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

freqcomm_gen:freqcomm_gen.cpp.o
	$(CXX) $(LDFLAGS) -lx86_adapt -lpaett_freqmod $^ ../src/CallingContextTree.cpp.o -o $(BINFOLD)/$@

paett_read_profile:paett_read_profile.cpp.o
	$(CXX) $(LDFLAGS) $^ ../src/CallingContextTree.cpp.o -o $(BINFOLD)/$@

filter_significant_profile:filter_significant_profile.cpp.o
	$(CXX) $(LDFLAGS) $^ ../src/CallingContextTree.cpp.o -o $(BINFOLD)/$@