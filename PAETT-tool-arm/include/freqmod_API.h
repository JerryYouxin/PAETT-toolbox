#ifndef __FREQMOD_API_H__
#define __FREQMOD_API_H__
#include <stdint.h>
#include <iostream>
#ifdef __cplusplus
extern "C" {
#endif

extern FILE* CPUSetList[64];
extern FILE* CPUCurList[64];

typedef struct MSR_UNCORE_RATIO_LIMIT_STRUCT
{
    uint64_t max:7;
    uint64_t rsv1:1;
    uint64_t min:7;
    uint64_t rsv2:49;
} MSR_UNCORE_RATIO_LIMIT_T;

inline uint64_t MAKE_UNCORE_VALUE_BY_FREQ(uint64_t freq) { 
    union{ MSR_UNCORE_RATIO_LIMIT_T u; uint64_t v; } ur; 
    ur.u.max=ur.u.min=freq; 
    ur.u.rsv1=ur.u.rsv2=0; 
    return ur.v; 
}

inline double DECODE_MAX_FREQ_FROM_UNCORE_VALUE(uint64_t uncore) {
    union{ MSR_UNCORE_RATIO_LIMIT_T u; uint64_t v; } ur;
    ur.v = uncore;
    return (double)ur.u.max / 10.0;
}

inline double DECODE_FREQ_FROM_CORE_VALUE(uint64_t core) {
    return (double)core / (double)1e6;
}

// Round to 1e5
inline uint64_t MAKE_CORE_VALUE_FROM_FREQ(double freq) {
    uint64_t core = (uint64_t)(freq*10);
    return (uint64_t)(core+((freq>((double)core/10.0))?1:0)) * 1e5;
}

void PAETT_init();
void PAETT_finalize();

// information query interface
int PAETT_getNCPU();
int PAETT_getNPKG();
void PAETT_getCoreFreq(int i, uint64_t *core);
void PAETT_getCoreFreqSetting(int i, uint64_t *core);
void PAETT_getUncoreFreq(int i, uint64_t *uncore);
void PAETT_getFreq(uint64_t* core, uint64_t* uncore);

// config all
void PAETT_modFreq(uint64_t coreFreq, uint64_t uncoreFreq);
void PAETT_modCoreFreq(uint64_t coreFreq);
void PAETT_modUncoreFreq(uint64_t uncoreFreq);
void PAETT_modFreqAll(uint64_t coreFreq, uint64_t uncoreFreq);
void PAETT_modCoreFreqAll(uint64_t coreFreq);
void PAETT_modUncoreFreqAll(uint64_t uncoreFreq);

// thread
void PAETT_inst_thread_init(uint64_t key);
void PAETT_inst_thread_fini(uint64_t key);
void PAETT_modOMPThread(uint64_t n);

// timers
void PAETT_time_begin(uint64_t key);
void PAETT_time_end(uint64_t key);
#ifdef __cplusplus
}
#endif
#endif
