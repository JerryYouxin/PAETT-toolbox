#ifndef __ENERGY_UTILS_H__
#define __ENERGY_UTILS_H__
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// #define ENABLE_DEBUG_LOG
#ifdef ENABLE_DEBUG_LOG
FILE* RAPL_LOG;
#define RAPL_LOG_FN "energy_utils.log"
#define RLOG_INIT do { RAPL_LOG = fopen(RAPL_LOG_FN, "a+"); if(!RAPL_LOG) printf("Error to open RAPL_LOG: %s\n", RAPL_LOG_FN); } while(0)
#define RLOG(msg, ...) if(RAPL_LOG) fprintf(RAPL_LOG, msg, ##__VA_ARGS__)
#define RLOG_FINI fclose(RAPL_LOG)
#else
#define RLOG_INIT 
#define RLOG(msg, ...) 
#define RLOG_FINI 
#endif

extern "C" {
//#include <x86_energy.h>
}
/*******************************************************************************************
 * x86_energy can access intel_powerclamp, intel_rapl_perf, msr/msr-safe, x86_adapt et.al. *
 * The access delay of these interfaces tested in our local machine results as follows:    *
 * x86_adapt < msr/msr-safe < intel_rapl_perf < intel_powerclamp                           *
 * To minimize the energy profiling overhead, this wrapper will try to use the fastest     *
 * x86_adapt as energy counters and read energy values by x86_energy library API           *
 *******************************************************************************************/

#define MAX_COUNTER_NUM 10


inline int energy_init() {
    return 0;
}

inline double get_pkg_energy() {
    return 0.0;
}

inline void energy_finalize() {
}

#endif
