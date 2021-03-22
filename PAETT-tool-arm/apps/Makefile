all: freq_read freq_set freq_cur

CXX=g++
CC=gcc

CFLAGS=-fopenmp -O3 -g -I../include
CXXFLAGS=-fopenmp -O3 -g -std=c++11 -I../include -fpermissive
LDFLAGS=-fopenmp -O3 -g 
BINFOLD=../bin

LIBS=../src/libpaett_freqmod_arm.cpp.o

%.c.o:%.c
	$(CC) $(CFLAGS) -c $< -o $@

%.cpp.o:%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

#collect_energy:collect_energy.cpp.o
#	$(CXX) $(LDFLAGS) $^ $(LIBS) -o $(BINFOLD)/$@

freq_read:freq_read.cpp.o
	$(CXX) $(LDFLAGS) $^ $(LIBS) -o $(BINFOLD)/$@

freq_set:freq_set.cpp.o
	$(CXX) $(LDFLAGS) $^ $(LIBS) -o $(BINFOLD)/$@

freq_cur:freq_cur.cpp.o
	$(CXX) $(LDFLAGS) $^ $(LIBS) -o $(BINFOLD)/$@

clean:
	rm -rf *.o
