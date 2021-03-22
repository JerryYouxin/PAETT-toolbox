all: freqcomm_gen paett_read_profile filter_significant_profile filter_gen

CXX=g++
CC=gcc

CFLAGS=-fopenmp -O3 -g -I../include
CXXFLAGS=-fopenmp -O3 -g -std=c++11 -I../include
LDFLAGS=-fopenmp -O3 -g -L../lib/
BINFOLD=../bin

%.c.o:%.c
	$(CC) $(CFLAGS) -c $< -o $@

%.cpp.o:%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

freqcomm_gen:freqcomm_gen.cpp.o
	$(CXX) $(LDFLAGS) $^ -lpaett_freqmod_arm ../src/CallingContextTree.cpp.o -o $(BINFOLD)/$@

paett_read_profile:paett_read_profile.cpp.o
	$(CXX) $(LDFLAGS) $^ ../src/CallingContextTree.cpp.o -o $(BINFOLD)/$@

filter_significant_profile:filter_significant_profile.cpp.o
	$(CXX) $(LDFLAGS) $^ ../src/CallingContextTree.cpp.o -o $(BINFOLD)/$@

filter_gen:filter_gen.cpp.o
	$(CXX) $(LDFLAGS) $^ ../src/CallingContextTree.cpp.o -o $(BINFOLD)/$@

clean:
	rm -rf *.o
