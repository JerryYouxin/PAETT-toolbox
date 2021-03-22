CXX=g++
CC=gcc

CFLAGS=-fopenmp -O3 -g -fpic -I../include -fpermissive
CXXFLAGS=-fopenmp -O3 -g -fpic -std=c++11 -I../include -fpermissive
LDFLAGS=-fopenmp -O3 -g -flto

LIBFOLD=../lib

# all:config.h libpaett_freqmod.so libpaett_freqmod_cct.so libcollect_energy.so libpaett_inst.so libpaett_inst_freqmod_cct.so
all:config.h libpaett_freqmod_arm.so libpaett_freqmod_cct.so libpaett_inst.so

%.c.o:%.c
	$(CC) $(CFLAGS) -c $< -o $@

%.cpp.o:%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

config.h: libpaett_freqmod_arm.so config_gen
#	./config_gen

config_gen: config_gen.cpp.o
	$(CXX) $(LDFLAGS) $^ $(LIBFOLD)/libpaett_freqmod_arm.so -lpapi -o $@

libpaett_freqmod_arm.so:libpaett_freqmod_arm.cpp.o CallingContextTree.cpp.o
	$(CXX) $(LDFLAGS) -shared $^ -o $(LIBFOLD)/$@

libpaett_inst.so:libpaett_inst.cpp.o CallingContextTree.cpp.o
	$(CXX) $(LDFLAGS) -shared $^ -o $(LIBFOLD)/$@

libpaett_freqmod_cct.so:libpaett_freqmod_cct.cpp.o CallingContextTree.cpp.o
	$(CXX) $(LDFLAGS) -shared $^ -o $(LIBFOLD)/$@

# libpaett_inst.freqmod.o:libpaett_inst.cpp
# 	$(CXX) $(CXXFLAGS) -DUSE_FREQMOD_CCT -c libpaett_inst.cpp -o $@

# libpaett_inst_freqmod_cct.so:libpaett_inst.freqmod.o CallingContextTree.cpp.o
# 	$(CXX) $(LDFLAGS) -shared $^ -o $(LIBFOLD)/$@

# libcollect_energy.so:libcollect_energy.cpp.o CallingContextTree.cpp.o
# 	$(CXX) $(LDFLAGS) -shared $^ -o $(LIBFOLD)/$@

clean:
	rm -rf *.o 
