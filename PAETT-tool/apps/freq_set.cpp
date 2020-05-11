#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
// extern uint64_t MAKE_UNCORE_VALUE_BY_FREQ(uint64_t freq);
#include "freqmod.h"
#include "freqmod_API.h"
#define USAGE printf("Usage: freq_set <core> <uncore>, where core is 12-24 (step 1) and uncore is 10-25 (step 1)\n")
int main(int argc,char *argv[]) {
    int i;
    if(argc!=3) {
        printf("Error: argc=%d:",argc);
        for(i=0;i<argc;++i) printf("%s ",argv[i]);
        printf("\n");
        USAGE;
        return 0;
    }
    int core, uncore;
    core = atoi(argv[1]);
    uncore = atoi(argv[2]);
    PAETT_init();
    PAETT_modFreqAll(core*1e5,MAKE_UNCORE_VALUE_BY_FREQ(uncore));
    PAETT_finalize();
    return 0;
}
