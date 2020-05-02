all: freq_read freq_set freq_overhead freq_cur

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

freq_read:freq_read.cpp.o
	$(CXX) $(LDFLAGS) -lx86_adapt ../src/libpaett_freqmod.cpp.o $^ -o $(BINFOLD)/$@

freq_set:freq_set.cpp.o
	$(CXX) $(LDFLAGS) -lx86_adapt ../src/libpaett_freqmod.cpp.o $^ -o $(BINFOLD)/$@

freq_overhead:freq_read.cpp.o
	$(CXX) $(LDFLAGS) -lx86_adapt ../src/libpaett_freqmod.cpp.o $^ -o $(BINFOLD)/$@

freq_cur:freq_cur.cpp.o
	$(CXX) $(LDFLAGS) -lx86_adapt ../src/libpaett_freqmod.cpp.o $^ -o $(BINFOLD)/$@

clean:
	rm -rf *.o