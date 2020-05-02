#include <stdint.h>
#include <fcntl.h>
#include <stdio.h>
#include <assert.h>
#include<sys/time.h>
#include <time.h>
#include <omp.h>
#include <math.h>
#include <stdlib.h>
#include <unistd.h>

#include <freqmod.h>
#include <freqmod_API.h>

#define max(a,b) ((a)>(b)?(a):(b))

struct config_metric_struct {
    uint64_t core_max, core_min;
    uint64_t uncore_max, uncore_min;
    uint64_t overhead;
    uint64_t core_latency_max;
    uint64_t core_latency_min;
    double core_latency_avg;
    uint64_t uncore_latency_max;
    uint64_t uncore_latency_min;
    double uncore_latency_avg;
} config_metric;

void generate_config() {
    printf("Generating config.h ...\n");
    FILE* fp = fopen("../include/config.h", "w");
    if(fp==NULL) {
        printf("Could not open config.h!\n");
        exit(1);
    }
    const uint64_t alpha = 10;
    const uint64_t factor = 2;
    uint64_t latency = max(config_metric.core_latency_max, config_metric.uncore_latency_max);
    fprintf(fp, "#ifndef __CONFIG_H__\n");
    fprintf(fp, "#define __CONFIG_H__\n");
    fprintf(fp, "/* Auto Generated Configurations for PAETT */\n");
    fprintf(fp, "/* Available Frequency Info in 100 MHz */\n");
    fprintf(fp, "#define MAX_CORE_FREQ %ld\n", config_metric.core_max);
    fprintf(fp, "#define MIN_CORE_FREQ %ld\n", config_metric.core_min);
    fprintf(fp, "#define MAX_UNCORE_FREQ %ld\n", config_metric.uncore_max);
    fprintf(fp, "#define MIN_UNCORE_FREQ %ld\n", config_metric.uncore_min);
    fprintf(fp, "#define STEP_CORE_FREQ %ld\n", 1);
    fprintf(fp, "#define STEP_UNCORE_FREQ %ld\n", 1);
    fprintf(fp, "/* All values are times in microseconds (us). */\n");
    fprintf(fp, "#define OVERHEAD %ld\n", config_metric.overhead);
    fprintf(fp, "#define CORE_LATENCY_MAX %ld\n", config_metric.core_latency_max);
    fprintf(fp, "#define CORE_LATENCY_MIN %ld\n", config_metric.core_latency_min);
    fprintf(fp, "#define CORE_LATENCY_AVG %lf\n", config_metric.core_latency_avg);
    fprintf(fp, "#define UNCORE_LATENCY_MAX %ld\n", config_metric.uncore_latency_max);
    fprintf(fp, "#define UNCORE_LATENCY_MIN %ld\n", config_metric.uncore_latency_min);
    fprintf(fp, "#define UNCORE_LATENCY_AVG %lf\n", config_metric.uncore_latency_avg);
    fprintf(fp, "#define LATENCY %ld\n", latency);
    fprintf(fp, "#define PRUNE_THRESHOLD %ld\n", max(factor*latency, alpha*config_metric.overhead));
    fprintf(fp, "#endif\n");
    fclose(fp);
}

void measure_freq_range() {
    printf("Measuring available frequency range ...\n");
    // TODO: auto detection
    config_metric.core_max = 22;
    config_metric.core_min = 8;
    config_metric.uncore_min = 7;
    config_metric.uncore_max = 20;
}

void measure_overhead(int n_iter) {
    printf("Measuring time overhead of libpaett_freqmod API calls ...\n");
    config_metric.overhead = 0;
    struct timespec t0,t1;
    clock_gettime(CLOCK_REALTIME,&t0);
    for(int i=0;i<n_iter;++i) {
        PAETT_modFreqAll( MAKE_CORE_VALUE_FROM_FREQ(config_metric.core_min/10.0),  MAKE_UNCORE_VALUE_BY_FREQ(config_metric.uncore_min));
        PAETT_modFreqAll( MAKE_CORE_VALUE_FROM_FREQ(config_metric.core_max/10.0),  MAKE_UNCORE_VALUE_BY_FREQ(config_metric.uncore_max));
    }
    clock_gettime(CLOCK_REALTIME,&t1);
    uint64_t mtime = (t0.tv_sec * 1000000000LL + t0.tv_nsec);
    uint64_t mtime2= (t1.tv_sec * 1000000000LL + t1.tv_nsec);
    config_metric.overhead = (uint64_t)((double)(mtime2-mtime) / (double)(2*n_iter)) / 1000;
}

uint64_t __measure_core_latency_once(uint64_t freq) {
    struct timespec t0,t1;
    uint64_t core, ncpu = PAETT_getNCPU();
    PAETT_modCoreFreqAll(freq);
    clock_gettime(CLOCK_REALTIME,&t0);
    for(int i=0;i<ncpu;++i) {
        PAETT_getCoreFreq(i, &core);
        while(core!=freq) {
            PAETT_getCoreFreq(i, &core);
        }
    }
    clock_gettime(CLOCK_REALTIME,&t1);
    uint64_t mtime = (t0.tv_sec * 1000000000LL + t0.tv_nsec);
    uint64_t mtime2= (t1.tv_sec * 1000000000LL + t1.tv_nsec);
    return mtime2-mtime;
}

void measure_core_latency(int n_iter) {
    printf("Measuring core frequency scaling latency ...\n");
    uint64_t latency, latency_sum = 0;
    config_metric.core_latency_max = 0;
    config_metric.core_latency_min = -1; // (uint64_t)(-1) is the maximum value of uint64_t data type
    for(int i=0;i<n_iter;++i) {
        latency = __measure_core_latency_once(MAKE_CORE_VALUE_FROM_FREQ(config_metric.core_min/10.0));
        latency_sum += latency;
        if(config_metric.core_latency_max < latency) config_metric.core_latency_max = latency;
        if(config_metric.core_latency_min > latency) config_metric.core_latency_min = latency;
        latency = __measure_core_latency_once(MAKE_CORE_VALUE_FROM_FREQ(config_metric.core_max/10.0));
        latency_sum += latency;
        if(config_metric.core_latency_max < latency) config_metric.core_latency_max = latency;
        if(config_metric.core_latency_min > latency) config_metric.core_latency_min = latency;
    }
    config_metric.core_latency_avg = (uint64_t)((double)latency_sum / (double)(n_iter*2)) / 1000;
    config_metric.core_latency_max/= 1000;
    config_metric.core_latency_min/= 1000;
}

void measure_uncore_latency(int n_iter) {
    // UNCORE frequency scaling is very fast and can not measure the latency from software now.
    // printf("Measuring uncore frequency scaling latency ...\n");
    config_metric.uncore_latency_avg = 0;
    config_metric.uncore_latency_max = 0;
    config_metric.uncore_latency_min = 0;
}

int main() {
    PAETT_init();
    measure_freq_range();
    measure_overhead(500);
    measure_core_latency(500);
    measure_uncore_latency(500);
    generate_config();
    PAETT_finalize();
}