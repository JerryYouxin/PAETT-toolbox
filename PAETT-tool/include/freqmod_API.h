#ifndef __FREQMOD_API_H__
#define __FREQMOD_API_H__
#include <stdint.h>
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
#endif