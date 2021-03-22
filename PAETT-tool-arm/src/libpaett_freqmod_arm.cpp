// freq_mod for arm cpu

#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>
#include <string>
#include <memory.h>
#include <omp.h>
#include <iostream>
using std::string;
//using namespace std;

#include <freqmod_API.h>

#ifdef USE_CPU_BIND
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#include <sched.h>
#undef _GNU_SOURCE
#else
#include <sched.h>
#endif
#endif

//#define MEASURE_OVERHEAD
#define E_X86_ADAPT_FAIL 1

#define __NEWER_THAN_Ivy_Btridge

#define REPORT_ERROR(msg) fprintf(stderr, "ERROR in %s:%d: %s", __FILE__, __LINE__, msg)
#define CHECK_VALID_FD(x,msg) do { if((x)<0) { REPORT_ERROR(msg); exit(-1); } } while(0)

#define MAKE_PSTATE_FROM_FREQ(x) ((x)/100000LL)
#define MAKE_FREQ_FROM_PSTATE(x) ((x)*100000LL)

static int initialized = 0;

static int ncpu = 64;
static int ndie = 0;
static int* cpuList = NULL;
static int* dieList = NULL;

static int* last_core;
static int* last_uncore;

FILE* CPUSetList[64];
FILE* CPUCurList[64];

// x86 core,uncore,cpuinfo
void PAETT_init() {
    for (int i = 0; i < ncpu; i++) {
        string file1("/sys/devices/system/cpu/cpu");
        string file2("/cpufreq/scaling_setspeed");
        string file3("/cpufreq/cpuinfo_cur_freq");
        string setfile;
        string curfile;
        curfile = file1 + std::to_string(i) + file3;
        setfile = file1 + std::to_string(i) + file2;

        CPUSetList[i] = fopen(setfile.c_str(), "w");
        CPUCurList[i] = fopen(curfile.c_str(), "r");

    }
    // cache device desc
    initialized = 1;
    last_core = (int*)malloc(ncpu*sizeof(int));
    for (int i = 0; i < ncpu; i++) {
        last_core[i] = 0;
    }
}

void PAETT_finalize() {
#ifdef USE_DYNAMIC_TUNING
        __finalize_cothread_for_freqmod();
#endif
    if (initialized) {
        for (int i = 0; i < ncpu; i++){
            fclose(CPUSetList[i]);
            fclose(CPUCurList[i]);
        }
    }
    initialized = 0;
}

int PAETT_getNCPU() {
    return ncpu;
}

int PAETT_getNPKG() {
    return ndie;
}

void PAETT_getCoreFreq(int i, uint64_t *core) {
    if (!initialized) return;
    uint64_t frequency;
    fflush(CPUCurList[i]);
    fseek(CPUCurList[i], 0, SEEK_SET);
    fscanf(CPUCurList[i] , "%ld" , &frequency );
    // TODO(xzb)
    *core = frequency;
}
void PAETT_getCoreFreqSetting(int i, uint64_t *core) {
    if(!initialized) return;
    uint64_t frequency;
    fflush(CPUCurList[i]);
    fseek(CPUCurList[i], 0, SEEK_SET);
    fscanf( CPUCurList[i] , "%ld" , &frequency );
    *core = frequency;
}

void PAETT_getUncoreFreq(int i, uint64_t *uncore) {
    *uncore = 0;
}

void PAETT_getFreq(uint64_t* core, uint64_t* uncore) {
    if(!initialized) return;
    for(int i = 0; i < ncpu; ++i) {
        PAETT_getCoreFreq(i, &core[i]);
    }
    for(int i = 0; i < ndie; ++i) {
        PAETT_getUncoreFreq(i, &uncore[i]);
    }
}

// TODO(xzb)
uint64_t PAETT_get_ncpu() {
    return ncpu;
}

uint64_t PAETT_get_ndie() {
    return ndie;
}

// config all
void PAETT_modCoreFreqAll(uint64_t coreFreq) {
    if(!initialized) return;
    if(omp_in_parallel()) return;
    for(int i = 0; i < ncpu; i++){
        fseek(CPUSetList[i], 0, SEEK_SET);
        fprintf(CPUSetList[i], "%ld", coreFreq);
        fflush(CPUSetList[i]);
        last_core[i] = coreFreq;
    }
    
}

void PAETT_modFreqAll(uint64_t coreFreq, uint64_t uncoreFreq) {
    if(!initialized) return;
    if(omp_in_parallel()) return;
    int i = 0;
    if(coreFreq && last_core[i]!=coreFreq) {
        PAETT_modCoreFreqAll(coreFreq);
    }
}

void PAETT_modFreq(uint64_t coreFreq, uint64_t uncoreFreq) {
    PAETT_modFreqAll(coreFreq, uncoreFreq);
}

void PAETT_modCoreFreq(int i, uint64_t coreFreq) {
    if(!initialized) return;
    if(coreFreq && last_core[i]!=coreFreq) {
        //uint64_t pstate = MAKE_PSTATE_FROM_FREQ(coreFreq);
        fseek(CPUSetList[i], 0, SEEK_SET);
        fprintf(CPUSetList[i],"%ld",coreFreq);
        fflush(CPUSetList[i]);
        last_core[i] = coreFreq;
    }
}


void PAETT_modUncoreFreq(int i, uint64_t uncoreFreq) {
}
// frequency modification with x86_adapt


void PAETT_modUncoreFreqAll(uint64_t uncoreFreq) {
}


// timers
void PAETT_time_begin(uint64_t key) {
    // DO NOTHING
    return;
}
void PAETT_time_end(uint64_t key) {
    // DO NOTHING
    return;
}

void PAETT_modOMPThread(uint64_t n) {
    omp_set_num_threads(n);
}

#ifdef MEASURE_LATENCY
#include<time.h>
int main() {
    int i;
    uint64_t cur_core;
    struct timespec t0,t1,t2,t3,tt;
    printf("begin init\n");

    PAETT_init();
    PAETT_modFreqAll(2200000,0);

    sleep(1);
    printf("Now begin measuing dvfs latency using fprint\n");
    
    // core
    clock_gettime(CLOCK_REALTIME,&tt);
    PAETT_modFreqAll(1500000,0);
    clock_gettime(CLOCK_REALTIME,&t0);
    
    
    
    for(i=0;i<ncpu;++i) {
        PAETT_getCoreFreq(i,&cur_core);
        while(cur_core<1500000-5000 || cur_core>1500000+5000) {
            PAETT_getCoreFreq(i,&cur_core);
            // printf("CUR CORE FREQ: %ld \n",cur_core);
        }
    }
    
    clock_gettime(CLOCK_REALTIME,&t1);
    PAETT_getCoreFreq(0, &cur_core);
    PAETT_modFreqAll(2200000, 0);
    clock_gettime(CLOCK_REALTIME, &t2);
    
    uint64_t mtime0= (tt.tv_sec * 1000000000LL + tt.tv_nsec);
    uint64_t mtime = (t0.tv_sec * 1000000000LL + t0.tv_nsec);
    uint64_t mtime2= (t1.tv_sec * 1000000000LL + t1.tv_nsec);
    uint64_t mtime3= (t2.tv_sec * 1000000000LL + t2.tv_nsec);
    printf("DVFS Using fprint Latency: %.2lf us, Overhead %.2lf us\n",
        (double)((mtime2-mtime)-(mtime3-mtime2))/1000.0, (mtime-mtime0)/1000.0);
    
    //last
    PAETT_modFreqAll(2200000,0);

    PAETT_finalize();
}
#endif
