#include <stdint.h>
#include <stdio.h>
#include "freqmod.h"
uint64_t core[28]={0};
uint64_t uncore[28]={0};
int main() {
    PAETT_init();
    int ncpu = PAETT_getNCPU();
    int npkg = PAETT_getNPKG();
    int i;
    printf("========= %d CPU Cores ========\n",ncpu);
    for(i=0; i<ncpu; ++i) {
        uint64_t core, coreset;
        PAETT_getCoreFreq(i, &core);
        PAETT_getCoreFreqSetting(i, &coreset);
        printf("CPU [%d] Core Frequency Setting: %.1lf GHz (cur freq=%.1lf GHz)\n", i, DECODE_FREQ_FROM_CORE_VALUE(coreset), DECODE_FREQ_FROM_CORE_VALUE(core));
    }
    printf("======= %d CPU Packages =======\n",npkg);
    for(i=0; i<npkg; ++i) {
        uint64_t uncore;
        PAETT_getUncoreFreq(i, &uncore);
        union{ MSR_UNCORE_RATIO_LIMIT_T u; uint64_t v; } ur;
        ur.v = uncore;
        printf("CPU [%d] Uncore Frequency Setting: %.1lf GHz, %.1lf GHz\n", i, ur.u.min/10.0, ur.u.max/10.0);
    }
    printf("===============================\n");
    PAETT_finalize();
    return 0;
}
