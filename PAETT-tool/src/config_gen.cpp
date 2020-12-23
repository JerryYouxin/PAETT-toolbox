#include <string.h>    // for strerror()
#include <errno.h>
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

#include <freqmod_API.h>

#include <string>

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
    uint64_t ncpu;
} config_metric;

void generate_config() {
    printf("Generating config.h ...\n");
    const uint64_t alpha = 50; // we consider overhead <= 2% is reasonable
    const uint64_t factor = 10;
    uint64_t latency = max(config_metric.core_latency_max, config_metric.uncore_latency_max);
    errno=0;
    FILE* fp = fopen("../include/config.h", "w");
    if(fp==NULL || errno) {
        fprintf(stderr, "Could not open config.h for writing: %s\n", strerror(errno));
        exit(1);
    }
    
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
    fprintf(fp, "#define NCPU %ld\n", config_metric.ncpu);
    fprintf(fp, "#endif\n");
    fclose(fp);
}

#define U_MSR_PMON_FIXED_CTL 0x703
#define U_MSR_PMON_FIXED_CTR 0x704
#define UNCORE_CLK_MASK (uint64_t)(1<<22)
// 10ms
#define EST_TIME_US 10000
#define EST_TIME_S  (EST_TIME_US*1e-6)

#define REPORT_ERROR(msg) fprintf(stderr, "ERROR in %s:%d: %s", __FILE__, __LINE__, msg)
#define CHECK_VALID_FD(x,msg) do { if((x)<0) { REPORT_ERROR(msg); exit(-1); } } while(0)

#define CHECK(stmt) do { if(stmt!=0) {printf("%s Failed!\n",#stmt); exit(-1);} } while(0)
#define RESET_FD(fd) lseek(fd, 0, SEEK_SET)

static int* msr_fd;

int init_msr() {
    msr_fd = new int[PAETT_getNCPU()];
    int i; char buff[20];
    for (i = 0; i < PAETT_getNCPU(); i++) {
        snprintf(buff, 20, "/dev/cpu/%d/msr", i);
        msr_fd[i] = open(buff, O_RDWR);
        CHECK_VALID_FD(msr_fd[i],"Failed to open msr!\n");
    }
    return 0;
}
void fin_msr() {
    int i;
    for(i=0;i<PAETT_getNCPU();++i) {
        close(msr_fd[i]);
    }
    delete[] msr_fd;
}

int read_msr_by_idx(int dev_idx, off_t msr, uint64_t *val)
{
    int rc;
    int fileDescriptor = msr_fd[dev_idx];
    RESET_FD(fileDescriptor);
    rc = pread(fileDescriptor, (void*)val, (size_t)sizeof(uint64_t), msr);
    if (rc != sizeof(uint64_t))
    {
        printf("read_msr_by_idx(): Pread failed\n");
        return -1;
    }
    return 0;
}

inline int write_msr_by_idx(int dev_idx, off_t msr, uint64_t val)
{
    int rc;
    int fileDescriptor = msr_fd[dev_idx];
    RESET_FD(fileDescriptor);
    rc = pwrite(fileDescriptor, &val, (size_t)sizeof(uint64_t), msr);
    if (rc != sizeof(uint64_t))
    {
        printf("write_msr_by_idx(): Pwrite failed\n");
        return -1;
    }
    return 0;
}

double get_cur_uncore_freq() {
    // read msr
    uint64_t uclk_b, uclk_e;
    read_msr_by_idx(0,U_MSR_PMON_FIXED_CTR,&uclk_b);
    usleep(EST_TIME_US);
    read_msr_by_idx(0,U_MSR_PMON_FIXED_CTR,&uclk_e);
    //printf("%ld %ld, %ld\n",uclk_b, uclk_e, EST_TIME_S);
    return ((double)(uclk_e-uclk_b))/(double)EST_TIME_S/1e9;
}

void disableTurbo() {
    init_msr();
    for(int i=0;i<PAETT_getNCPU();++i)
        write_msr_by_idx(i,0x1a0,0x4000850089);
    fin_msr();
}

void enableTurbo() {
    init_msr();
    for(int i=0;i<PAETT_getNCPU();++i)
        write_msr_by_idx(i, 0x1a0, 0x850089);
    fin_msr();
}

/* Core frequency range can be automatically parsed from the output of lscpu command. */
void detect_core_range() {
    FILE* pp;
    if( (pp = popen("lscpu", "r")) == NULL ) {
        printf("popen(\"lscpu\", \"r\") error!/n");
        exit(1);
    }
    char * line = NULL;
    size_t len = 0;
    ssize_t read;
    std::size_t found;
    double fmax, fmin;
    while ((read = getline(&line, &len, pp)) != -1) {
        std::string s(line);
        found = s.find("CPU max MHz:");
        if (found!=std::string::npos) {
            sscanf(line, "CPU max MHz:           %lf", &fmax);
        }
        found = s.find("CPU min MHz:");
        if (found!=std::string::npos) {
            sscanf(line, "CPU min MHz:           %lf", &fmin);
        }
        found = s.find("CPU(s):");
        if (found!=std::string::npos) {
            sscanf(line, "CPU(s):                %ld", &config_metric.ncpu);
        }
    }
    config_metric.core_min = (uint64_t)(fmin/100);
    config_metric.core_max = (uint64_t)(fmax/100);
    printf("Detected core frequency min: %ld\n",config_metric.core_min);
    printf("Detected core frequency max: %ld\n",config_metric.core_max);
}

/* Uncore frequency range detection. We assume that the available 
   uncore is in 100 MHz step, and we try each configurations from 
   100 MHz to higher to find the available configuration range. */
void detect_uncore_range() {
    init_msr();
    // enable uncore clk
    uint64_t en;
    read_msr_by_idx(0,U_MSR_PMON_FIXED_CTL,&en);
    write_msr_by_idx(0, U_MSR_PMON_FIXED_CTL, (en|UNCORE_CLK_MASK));
    config_metric.uncore_min = 1;
    while(1) {
        printf("[INFO] Checking %d...", config_metric.uncore_min);
        PAETT_modUncoreFreqAll(MAKE_UNCORE_VALUE_BY_FREQ(config_metric.uncore_min));
        usleep(100);
        // as we only detecting the available configurations, so we just check one socket
        double cur = get_cur_uncore_freq();
        printf("Cur=%lf...",cur);
        uint64_t uncore = uint64_t(cur*10+0.5);
        if(uncore==config_metric.uncore_min) {
            printf("Success\n");
            break;
        }
        printf("Failed\n");
        config_metric.uncore_min++;
    }
    config_metric.uncore_max = config_metric.uncore_min;
    while(1) {
        printf("[INFO] Checking %d...", config_metric.uncore_max);
        PAETT_modUncoreFreqAll(MAKE_UNCORE_VALUE_BY_FREQ(config_metric.uncore_max));
        usleep(100);
        // as we only detecting the available configurations, so we just check one socket
        double cur = get_cur_uncore_freq();
        printf("Cur=%lf...",cur);
        uint64_t uncore = uint64_t(cur*10+0.5);
        if(uncore!=config_metric.uncore_max) {
            printf("Failed\n");
            break;
        }
        printf("Success\n");
        config_metric.uncore_max++;
    }
    // now we recover the maximum uncore configuration as the current value is invalid
    config_metric.uncore_max--;
    write_msr_by_idx(0, U_MSR_PMON_FIXED_CTL, (en));
    fin_msr();
    printf("Detected uncore frequency min: %ld\n",config_metric.uncore_min);
    printf("Detected uncore frequency max: %ld\n",config_metric.uncore_max);
}

void measure_freq_range() {
    printf("Measuring available frequency range ...\n");
#ifdef MANNUAL_CONFIG
    // TODO: auto detection
    config_metric.core_max = 22;
    config_metric.core_min = 8;
    config_metric.uncore_min = 7;
    config_metric.uncore_max = 20;
#else
    // auto detection of core/uncore frequency ranges
    //disableTurbo();
    //enableTurbo();
    detect_core_range();
    detect_uncore_range();
#endif
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