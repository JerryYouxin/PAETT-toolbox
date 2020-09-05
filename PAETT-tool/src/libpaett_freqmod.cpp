#include <freqmod.h>
#include <freqmod_API.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>
#include <x86_adapt.h>

#include <omp.h>

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

#define SUCCESS 0
#define E_X86_ADAPT_FAIL 1

static int initialized = 0;
static int x86_pstate_index;
static int x86_cur_pstate_index;
static int x86_uncore_min_index;
static int x86_uncore_max_index;
static int ncpu = 0;
static int ndie = 0;
static int* cpuList = NULL;
static int* dieList = NULL;

static int last_core;
static int last_uncore;

#define __NEWER_THAN_Ivy_Btridge

#define REPORT_ERROR(msg) fprintf(stderr, "ERROR in %s:%d: %s", __FILE__, __LINE__, msg)
#define CHECK_VALID_FD(x,msg) do { if((x)<0) { REPORT_ERROR(msg); exit(-1); } } while(0)

#ifdef __NEWER_THAN_Ivy_Btridge
#define MAKE_PSTATE_FROM_FREQ(x) (((x)/100000LL)<<8)
#define MAKE_FREQ_FROM_PSTATE(x) (((x)>>8)*100000LL)
#else
#define MAKE_PSTATE_FROM_FREQ(x) ((x)/100000LL)
#define MAKE_FREQ_FROM_PSTATE(x) ((x)*100000LL)
#endif

#ifdef USE_CPU_BIND
#include "config.h"
static int cpu_per_die = 0;
static int active_dies = 0;
// mask per die
static cpu_set_t* mask;
static int last_active_die;
static int min_pstate = MAKE_PSTATE_FROM_FREQ(MIN_CORE_FREQ*100000LL);
#endif

//#define USE_DYNAMIC_TUNING
#ifdef USE_DYNAMIC_TUNING
#include <pthread.h>
static int tuning;
static pthread_t tid;
static uint64_t core_request=0;
static uint64_t uncore_request=0;
// in us
#define DYN_TUNE_TIME_WINDOW 100

void* __dynamic_tuning(void* arg) {
    int i;
    while(tuning) {
        // extract requests
        uint64_t coreFreq = core_request;
        uint64_t uncoreFreq = uncore_request;
        if(coreFreq==last_core && uncoreFreq==last_uncore) {
            usleep(DYN_TUNE_TIME_WINDOW);
            continue;
        }
#ifndef MEASURE_OVERHEAD
        if(coreFreq && last_core!=coreFreq) {
#else
        coreFreq = 2400000;
        uncoreFreq = 6425;
#endif
            uint64_t pstate = MAKE_PSTATE_FROM_FREQ(coreFreq);
            for (i=0;i<ncpu;++i) {
                int ret = x86_adapt_set_setting(cpuList[i], x86_pstate_index, pstate);
                if (ret!=8) {
                    fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting core pstate failed: %d\n",ret);
                }
            }
            last_core = coreFreq;
#ifndef MEASURE_OVERHEAD
        }
        if(uncoreFreq && last_uncore!=uncoreFreq) {
#endif
            uint64_t uncore = uncoreFreq&0xff;
            for (i=0;i<ndie;++i) {
                int ret1 = x86_adapt_set_setting(dieList[i], x86_uncore_min_index, uncore);
                int ret2 = x86_adapt_set_setting(dieList[i], x86_uncore_max_index, uncore);
                if (ret1!=8 || ret2!=8) {
                    fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting uncore frequency failed: %d, %d\n",ret1, ret2);
                }
            }
            last_uncore = uncoreFreq;
#ifndef MEASURE_OVERHEAD
        }
#endif
    }
    return 0;
}

void __init_cothread_for_freqmod() {
    tuning = 1;
    pthread_create(&tid, NULL, __dynamic_tuning, NULL);
}

inline void __request_new_core_freq(uint64_t core) {
    core_request = core;
}

inline void __request_new_uncore_freq(uint64_t uncore) {
    uncore_request = uncore;
}

void __finalize_cothread_for_freqmod() {
    void* status;
    tuning = 0;
    pthread_join(tid,&status);
}
#endif
void PAETT_init() {
    int i;
    int ret = x86_adapt_init();
    if (ret) {
        fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_init failed: %d\n",ret);
        exit(E_X86_ADAPT_FAIL);
    }
    // core init
    x86_pstate_index = x86_adapt_lookup_ci_name(X86_ADAPT_CPU, "Intel_Target_PState");
    if (x86_pstate_index < 0) {
        fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_lookup_ci_name pstate failed: %d\n",x86_pstate_index);
        goto failed;
    }
    x86_cur_pstate_index = x86_adapt_lookup_ci_name(X86_ADAPT_CPU, "Intel_Current_PState");
    if (x86_cur_pstate_index < 0) {
        fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_lookup_ci_name pstate failed: %d\n",x86_cur_pstate_index);
        goto failed;
    }
    // uncore init
    x86_uncore_min_index = x86_adapt_lookup_ci_name(X86_ADAPT_DIE, "Intel_UNCORE_MIN_RATIO");
    if (x86_uncore_min_index < 0) {
        fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_lookup_ci_name uncore min failed: %d\n",x86_uncore_min_index);
        goto failed;
    }
    x86_uncore_max_index = x86_adapt_lookup_ci_name(X86_ADAPT_DIE, "Intel_UNCORE_MAX_RATIO");
    if (x86_uncore_max_index < 0) {
        fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_lookup_ci_name uncore max failed: %d\n",x86_uncore_max_index);
        goto failed;
    }
    // cpu detection
    ncpu = x86_adapt_get_nr_available_devices(X86_ADAPT_CPU);
    ndie = x86_adapt_get_nr_available_devices(X86_ADAPT_DIE);
    // cache device desc
    cpuList = (int*)malloc(ncpu*sizeof(int));
    dieList = (int*)malloc(ndie*sizeof(int));
    for (i=0;i<ncpu;++i) {
        cpuList[i] = x86_adapt_get_device(X86_ADAPT_CPU, i);
        CHECK_VALID_FD(cpuList[i], "x86_adapt_get_device for CPU failed");
    }
    for (i=0;i<ndie;++i) {
        dieList[i] = x86_adapt_get_device(X86_ADAPT_DIE, i);
        CHECK_VALID_FD(dieList[i], "x86_adapt_get_device for DIE failed");
    }
#ifdef USE_CPU_BIND
    // assume each die has the same number of cpus
    assert(ncpu % ndie==0);
    cpu_per_die = ncpu / ndie;
    active_dies = 1; // by default, the entry of main function is always in serial
    last_active_die = 0;
    // prepare for mask of CPU binding
    mask = (cpu_set_t*)malloc(sizeof(cpu_set_t)*ndie);
    for(i=0;i<ndie;++i) {
        CPU_ZERO(&mask[i]);
        int c;
        int e=i*cpu_per_die+cpu_per_die;
        for(c=0;c<e;++c) {
            CPU_SET(c, &mask[i]);
        }
    }
#endif
    last_core = 0;
    last_uncore = 0;
    initialized = 1;
#ifdef USE_DYNAMIC_TUNING
    __init_cothread_for_freqmod();
#endif
    return ;
failed:
    x86_adapt_finalize();
    exit(E_X86_ADAPT_FAIL);
}
void PAETT_finalize() {
    if(initialized) {
#ifdef USE_DYNAMIC_TUNING
        __finalize_cothread_for_freqmod();
#endif
        int i;
        initialized = 0;
        x86_adapt_finalize();
        for (i=0;i<ncpu;++i) {
            x86_adapt_put_device(X86_ADAPT_CPU, i);
            cpuList[i] = 0;
        }
        for (i=0;i<ndie;++i) {
            x86_adapt_put_device(X86_ADAPT_DIE, i);
            dieList[i] = 0;
        }
    }
}

int PAETT_getNCPU() {
    return ncpu;
}
int PAETT_getNPKG() {
    return ndie;
}

void PAETT_getCoreFreq(int i, uint64_t *core) {
    if(!initialized) return;
    uint64_t frequency;
    int result = x86_adapt_get_setting(cpuList[i], x86_cur_pstate_index, &frequency);
    if (result==8) {
        *core = MAKE_FREQ_FROM_PSTATE(frequency);
    } else {
        *core = 0;
    }
}

void PAETT_getCoreFreqSetting(int i, uint64_t *core) {
    if(!initialized) return;
    uint64_t frequency;
    int result = x86_adapt_get_setting(cpuList[i], x86_pstate_index, &frequency);
    if (result==8) {
        *core = MAKE_FREQ_FROM_PSTATE(frequency);
    } else {
        *core = 0;
    }
}

void PAETT_getUncoreFreq(int i, uint64_t *uncore) {
    if(!initialized) return;
    uint64_t frequency;
    union{ MSR_UNCORE_RATIO_LIMIT_T u; uint64_t v; } ur;
    int result = x86_adapt_get_setting(dieList[i], x86_uncore_max_index, &frequency);
    if (result==8) {
        ur.u.max = frequency;
    } else {
        ur.u.max = 0;
    }
    result = x86_adapt_get_setting(dieList[i], x86_uncore_min_index, &frequency);
    if (result==8) {
        ur.u.min = frequency;
    } else {
        ur.u.min = 0;
    }
    *uncore = ur.v;
}

void PAETT_getFreq(uint64_t* core, uint64_t* uncore) {
    if(!initialized) return;
    int i;
    for(i=0;i<ncpu;++i) {
        PAETT_getCoreFreq(i,&core[i]);
    }
    for(i=0;i<ndie;++i) {
        PAETT_getUncoreFreq(i,&uncore[i]);
    }
}

uint64_t PAETT_get_ncpu() {
    return ncpu;
}
uint64_t PAETT_get_ndie() {
    return ndie;
}
// config all
// deplicated implementation, USE PAET_mod...ALL version
void PAETT_modFreq(uint64_t coreFreq, uint64_t uncoreFreq) {
    PAETT_modFreqAll(coreFreq, uncoreFreq);
}
void PAETT_modCoreFreq(uint64_t coreFreq) {
    PAETT_modCoreFreqAll(coreFreq);
}
void PAETT_modUncoreFreq(uint64_t uncoreFreq) {
    PAETT_modUncoreFreqAll(uncoreFreq);
}
#ifdef USE_DYNAMIC_TUNING
// frequency modification request to cothread
void PAETT_modFreqAll(uint64_t coreFreq, uint64_t uncoreFreq) {
    if(!initialized) return;
    if(omp_in_parallel()) return;
    __request_new_core_freq(coreFreq);
    __request_new_uncore_freq(uncoreFreq);
}
void PAETT_modCoreFreqAll(uint64_t coreFreq) {
    if(!initialized) return;
    if(omp_in_parallel()) return;
    __request_new_core_freq(coreFreq);
}
void PAETT_modUncoreFreqAll(uint64_t uncoreFreq) {
    if(!initialized) return;
    if(omp_in_parallel()) return;
    __request_new_uncore_freq(uncoreFreq);
}
#else
#ifdef USE_CPU_BIND
void PAETT_modFreqAll(uint64_t coreFreq, uint64_t uncoreFreq) {
    if(!initialized) return;
    if(omp_in_parallel()) return;
    int i;
    if(coreFreq && (last_core!=coreFreq || last_active_die!=active_dies)) {
        uint64_t pstate = MAKE_PSTATE_FROM_FREQ(coreFreq);
        for (i=0;i<active_dies*cpu_per_die;++i) {
            int ret = x86_adapt_set_setting(cpuList[i], x86_pstate_index, pstate);
            if (ret!=8) {
                fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting core pstate failed: %d\n",ret);
            }
        }
        for (i=active_dies*cpu_per_die;i<ncpu;++i) {
            int ret = x86_adapt_set_setting(cpuList[i], x86_pstate_index, min_pstate);
            if (ret!=8) {
                fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting core pstate failed: %d\n",ret);
            }
        }
        last_core = coreFreq;
        last_active_die = active_dies;
    }
    if(uncoreFreq && (last_uncore!=uncoreFreq || last_active_die!=active_dies)) {
        uint64_t uncore = uncoreFreq&0xff;
        for (i=0;i<active_dies;++i) {
            int ret1 = x86_adapt_set_setting(dieList[i], x86_uncore_min_index, uncore);
            int ret2 = x86_adapt_set_setting(dieList[i], x86_uncore_max_index, uncore);
            if (ret1!=8 || ret2!=8) {
                fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting uncore frequency failed: %d, %d\n",ret1, ret2);
            }
        }
        for (i=active_dies;i<ncpu;++i) {
            int ret1 = x86_adapt_set_setting(dieList[i], x86_uncore_min_index, MIN_UNCORE_FREQ);
            int ret2 = x86_adapt_set_setting(dieList[i], x86_uncore_max_index, MIN_UNCORE_FREQ);
            if (ret1!=8 || ret2!=8) {
                fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting uncore frequency failed: %d, %d\n",ret1, ret2);
            }
        }
        last_uncore = uncoreFreq;
        last_active_die = active_dies;
    }
}
void PAETT_modCoreFreqAll(uint64_t coreFreq) {
    if(!initialized) return;
    if(omp_in_parallel()) return;
    int i;
    if(coreFreq && (last_core!=coreFreq || last_active_die!=active_dies)) {
        uint64_t pstate = MAKE_PSTATE_FROM_FREQ(coreFreq);
        for (i=0;i<active_dies*cpu_per_die;++i) {
            int ret = x86_adapt_set_setting(cpuList[i], x86_pstate_index, pstate);
            if (ret!=8) {
                fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting core pstate failed: %d\n",ret);
            }
        }
        for (i=active_dies*cpu_per_die;i<ncpu;++i) {
            int ret = x86_adapt_set_setting(cpuList[i], x86_pstate_index, min_pstate);
            if (ret!=8) {
                fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting core pstate failed: %d\n",ret);
            }
        }
        last_core = coreFreq;
        last_active_die = active_dies;
    }
}
void PAETT_modUncoreFreqAll(uint64_t uncoreFreq) {
    if(!initialized) return;
    if(omp_in_parallel()) return;
    int i;
    if(uncoreFreq && (last_uncore!=uncoreFreq || last_active_die!=active_dies)) {
        uint64_t uncore = uncoreFreq&0xff;
        for (i=0;i<active_dies;++i) {
            int ret1 = x86_adapt_set_setting(dieList[i], x86_uncore_min_index, uncore);
            int ret2 = x86_adapt_set_setting(dieList[i], x86_uncore_max_index, uncore);
            if (ret1!=8 || ret2!=8) {
                fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting uncore frequency failed: %d, %d\n",ret1, ret2);
            }
        }
        for (i=active_dies;i<ncpu;++i) {
            int ret1 = x86_adapt_set_setting(dieList[i], x86_uncore_min_index, MIN_UNCORE_FREQ);
            int ret2 = x86_adapt_set_setting(dieList[i], x86_uncore_max_index, MIN_UNCORE_FREQ);
            if (ret1!=8 || ret2!=8) {
                fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting uncore frequency failed: %d, %d\n",ret1, ret2);
            }
        }
        last_uncore = uncoreFreq;
        last_active_die = active_dies;
    }
}
#else
// frequency modification with x86_adapt
void PAETT_modFreqAll(uint64_t coreFreq, uint64_t uncoreFreq) {
    if(!initialized) return;
    if(omp_in_parallel()) return;
    int i;
#ifndef MEASURE_OVERHEAD
    if(coreFreq && last_core!=coreFreq) {
#else
    coreFreq = 2400000;
    uncoreFreq = 6425;
#endif
        uint64_t pstate = MAKE_PSTATE_FROM_FREQ(coreFreq);
        for (i=0;i<ncpu;++i) {
            int ret = x86_adapt_set_setting(cpuList[i], x86_pstate_index, pstate);
            if (ret!=8) {
                fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting core pstate failed: %d\n",ret);
            }
        }
        last_core = coreFreq;
#ifndef MEASURE_OVERHEAD
    }
    if(uncoreFreq && last_uncore!=uncoreFreq) {
#endif
        uint64_t uncore = uncoreFreq&0xff;
        for (i=0;i<ndie;++i) {
            int ret1 = x86_adapt_set_setting(dieList[i], x86_uncore_min_index, uncore);
            int ret2 = x86_adapt_set_setting(dieList[i], x86_uncore_max_index, uncore);
            if (ret1!=8 || ret2!=8) {
                fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting uncore frequency failed: %d, %d\n",ret1, ret2);
            }
        }
        last_uncore = uncoreFreq;
#ifndef MEASURE_OVERHEAD
    }
#endif
}
void PAETT_modCoreFreqAll(uint64_t coreFreq) {
    if(!initialized) return;
    if(omp_in_parallel()) return;
    int i;
#ifndef MEASURE_OVERHEAD
    if(coreFreq && last_core!=coreFreq) {
#else
    coreFreq = 2400000;
#endif
        uint64_t pstate = MAKE_PSTATE_FROM_FREQ(coreFreq);
        for (i=0;i<ncpu;++i) {
            int ret = x86_adapt_set_setting(cpuList[i], x86_pstate_index, pstate);
            if (ret!=8) {
                fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting core pstate failed: %d\n",ret);
            }
        }
        last_core = coreFreq;
#ifndef MEASURE_OVERHEAD
    }
#endif
}
void PAETT_modUncoreFreqAll(uint64_t uncoreFreq) {
    if(!initialized) return;
    if(omp_in_parallel()) return;
    int i;
#ifndef MEASURE_OVERHEAD
    if(uncoreFreq && last_uncore!=uncoreFreq) {
#else
    uncoreFreq = 6425;
#endif
        uint64_t uncore = uncoreFreq&0xff;
        for (i=0;i<ndie;++i) {
            int ret1 = x86_adapt_set_setting(dieList[i], x86_uncore_min_index, uncore);
            int ret2 = x86_adapt_set_setting(dieList[i], x86_uncore_max_index, uncore);
            if (ret1!=8 || ret2!=8) {
                fprintf(stderr,"[libpaett_freqmod_x86_adapt] Error: x86_adapt_set_setting uncore frequency failed: %d, %d\n",ret1, ret2);
            }
        }
        last_uncore = uncoreFreq;
#ifndef MEASURE_OVERHEAD
    }
#endif
}
#endif // USE_CPU_BIND
#endif // USE_DYNAMIC_TUNING
// timers
void PAETT_time_begin(uint64_t key) {
    // DO NOTHING
    return ;
}
void PAETT_time_end(uint64_t key) {
    // DO NOTHING
    return ;
}
void PAETT_modOMPThread(uint64_t n) {
#ifdef USE_CPU_BIND
    // calculate the number of active dies. Use upper bound
    active_dies = (n+cpu_per_die-1) / cpu_per_die;
    // binding sockets according to the active dies
    int result = sched_setaffinity(0, sizeof(mask[active_dies-1]), &mask[active_dies-1]);
#endif
#ifndef MEASURE_OVERHEAD
    omp_set_num_threads(n);
#else
    omp_set_num_threads(28);
#endif
}

#ifdef MEASURE_LATENCY
#include <time.h>
int main() {
    int i;
    uint64_t cur_core;
    struct timespec t0,t1,t2,t3,tt;
    PAETT_init();
    // reset
    PAETT_modCoreFreqAll(2400000);
    sleep(1);
    printf("Now begin measuing dvfs latency using x86_adapt\n");
    clock_gettime(CLOCK_REALTIME,&tt);
    PAETT_modCoreFreqAll(1500000);
    clock_gettime(CLOCK_REALTIME,&t0);
    for(i=0;i<ncpu;++i) {
        PAETT_getCoreFreq(i,&cur_core);
        while(cur_core!=1500000) {
            PAETT_getCoreFreq(i,&cur_core);
            // printf("CUR CORE FREQ: %ld \n",cur_core);
        }
    }
    clock_gettime(CLOCK_REALTIME,&t1);
    PAETT_getCoreFreq(0,&cur_core);
    clock_gettime(CLOCK_REALTIME,&t2);
    uint64_t mtime0= (tt.tv_sec * 1000000000LL + tt.tv_nsec);
    uint64_t mtime = (t0.tv_sec * 1000000000LL + t0.tv_nsec);
    uint64_t mtime2= (t1.tv_sec * 1000000000LL + t1.tv_nsec);
    uint64_t mtime3= (t2.tv_sec * 1000000000LL + t2.tv_nsec);
    printf("DVFS Using X86_adapt Latency: %.2lf us, Overhead %.2lf us\n",(double)((mtime2-mtime)-(mtime3-mtime2))/1000.0, (mtime-mtime0)/1000.0);
    PAETT_modCoreFreqAll(2400000);
    PAETT_finalize();
}
#endif