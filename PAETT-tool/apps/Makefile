all: freq_read freq_set freq_cur collect_energy

CXX=g++
CC=gcc

CFLAGS=-m64 -fopenmp -O3 -g -I../include
CXXFLAGS=-m64 -fopenmp -O3 -g -std=c++11 -I../include -fpermissive
LDFLAGS=-m64 -fopenmp -O3 -g 
BINFOLD=../bin

LIBS=../src/libpaett_freqmod.cpp.o -lx86_adapt -lx86_energy

%.c.o:%.c
	$(CC) $(CFLAGS) -c $< -o $@

%.cpp.o:%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

collect_energy:collect_energy.cpp.o
	$(CXX) $(LDFLAGS) $^ $(LIBS) -o $(BINFOLD)/$@

freq_read:freq_read.cpp.o
	$(CXX) $(LDFLAGS) $^ $(LIBS) -o $(BINFOLD)/$@

freq_set:freq_set.cpp.o
	$(CXX) $(LDFLAGS) $^ $(LIBS) -o $(BINFOLD)/$@

freq_cur:freq_cur.cpp.o
	$(CXX) $(LDFLAGS) $^ $(LIBS) -o $(BINFOLD)/$@

clean:
	rm -rf *.o