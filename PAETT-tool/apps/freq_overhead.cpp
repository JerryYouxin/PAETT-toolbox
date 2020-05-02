#include <stdint.h>
#include <omp.h>
#include <freqmod.h>
#include <freqmod_API.h>
#define NTIMES 10000
#define UNCORE MAKE_UNCORE_VALUE_BY_FREQ(10)
#define CORE 2400000
int main() {
    double s,e;
    s = omp_get_wtime();
    PAETT_init();
    e = omp_get_wtime();
    printf("PAETT_init overhead = %08lf\n",(e-s));
    int i;
    s = omp_get_wtime();
    for(i =0; i<NTIMES/2;++i) {
        PAETT_modFreq(CORE,UNCORE);
        PAETT_modFreq(1200000,MAKE_UNCORE_VALUE_BY_FREQ(11));
    }
    e = omp_get_wtime();
    printf("PAETT_modFreq overhead = %08lf (%lf/%d)\n",(e-s)/NTIMES,e-s,NTIMES);
    s = omp_get_wtime();
    for(i =0; i<NTIMES;++i)
        PAETT_modCoreFreq(CORE);
    e = omp_get_wtime();
    printf("PAETT_modCoreFreq overhead = %08lf (%lf/%d)\n",(e-s)/NTIMES,e-s,NTIMES);
    s = omp_get_wtime();
    for(i =0; i<NTIMES;++i)
        PAETT_modUncoreFreq(UNCORE);
    e = omp_get_wtime();
    printf("PAETT_modUncoreFreq overhead = %08lf (%lf/%d)\n",(e-s)/NTIMES,e-s,NTIMES);
    s = omp_get_wtime();
    for(i =0; i<NTIMES;++i)
        PAETT_modFreqAll(CORE, UNCORE);
    e = omp_get_wtime();
    printf("PAETT_modFreqAll overhead = %08lf (%lf/%d)\n",(e-s)/NTIMES,e-s,NTIMES);
    s = omp_get_wtime();
    for(i =0; i<NTIMES;++i)
        PAETT_modCoreFreqAll(CORE);
    e = omp_get_wtime();
    printf("PAETT_modCoreFreqAll overhead = %08lf (%lf/%d)\n",(e-s)/NTIMES,e-s,NTIMES);
    s = omp_get_wtime();
    for(i =0; i<NTIMES;++i)
        PAETT_modUncoreFreqAll(UNCORE);
    e = omp_get_wtime();
    printf("PAETT_modUncoreFreqAll overhead = %08lf (%lf/%d)\n",(e-s)/NTIMES,e-s,NTIMES);
    s = omp_get_wtime();
    for(i =0; i<NTIMES;++i)
        PAETT_modFreqPost(CORE, UNCORE);
    e = omp_get_wtime();
    printf("PAETT_modFreqPost overhead = %08lf (%lf/%d)\n",(e-s)/NTIMES,e-s,NTIMES);
    s = omp_get_wtime();
    for(i =0; i<NTIMES;++i)
        PAETT_modCoreFreqPost(CORE);
    e = omp_get_wtime();
    printf("PAETT_modCoreFreqPost overhead = %08lf (%lf/%d)\n",(e-s)/NTIMES,e-s,NTIMES);
    s = omp_get_wtime();
    for(i =0; i<NTIMES;++i)
        PAETT_modUncoreFreqPost(UNCORE);
    e = omp_get_wtime();
    printf("PAETT_modUncoreFreqPost overhead = %08lf (%lf/%d)\n",(e-s)/NTIMES,e-s,NTIMES);
    PAETT_modFreqAll(CORE, UNCORE);
    s = omp_get_wtime();
    PAETT_finalize();
    e = omp_get_wtime();
    printf("PAETT_finalize overhead = %08lf\n",(e-s));
    return 0;
}