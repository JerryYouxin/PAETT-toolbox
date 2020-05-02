#define _GNU_SOURCE
#include <sched.h>
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

#define REPORT_ERROR(msg) fprintf(stderr, "ERROR in %s:%d: %s", __FILE__, __LINE__, msg)
#define CHECK_VALID_FD(x,msg) do { if((x)<0) { REPORT_ERROR(msg); exit(-1); } } while(0)

#define CHECK(stmt) do { if(stmt!=0) {printf("%s Failed!\n",#stmt); exit(-1);} } while(0)
#define RESET_FD(fd) lseek(fd, 0, SEEK_SET)

#define N_CPU 128
static int msr_fd[N_CPU];

int init_msr() {
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

#define MSR_UNCORE_RATIO_LIMIT 0x620
#define U_MSR_PMON_FIXED_CTL 0x703
#define U_MSR_PMON_FIXED_CTR 0x704
#define UNCORE_CLK_MASK (uint64_t)(1<<22)
// 10ms
#define EST_TIME_US 10000
#define EST_TIME_S  (EST_TIME_US*1e-6)

#define TEST_CORE_FREQ 1500000
#define MAX_CORE_FREQ  2400000
#define FILENAME_SIZE 500

char cur_freq_filename[FILENAME_SIZE];
int cur_freq_fd;

#define RESET_FD(fd) lseek(fd, 0, SEEK_SET)
#define REPORT_ERROR(msg) fprintf(stderr, "ERROR in %s:%d: %s", __FILE__, __LINE__, msg)
#define CHECK_VALID_FD(x,msg) do { if((x)<0) { REPORT_ERROR(msg); exit(-1); } } while(0)
#define READ_CHECK_CPUFREQ(fd, buff, size) do { RESET_FD(fd); int rc = read(fd, buff, size); if (rc < 0) { printf("set_cpu_freq(): read failed : %d\n",rc); return -1; } } while(0)
#define WRITE_CHECK_CPUFREQ(fd, buff, size) do { RESET_FD(fd); int rc = write(fd, buff, size); if (rc < 0) { printf("set_cpu_freq(): write failed : %d\n",rc); return -1; } } while(0)

//#define USE_SELFDEF
#ifdef USE_SELFDEF
#error This method is wrong!!! Dont use it
#define CURFREQ_EST_INTERVAL 100000

#include <chrono>

int64_t nanos() {
    auto t = std::chrono::high_resolution_clock::now();
    return std::chrono::time_point_cast<std::chrono::nanoseconds>(t).time_since_epoch().count();
}

inline void busy_loop(uint64_t iters) {
    volatile int sink;
    do {
        sink = 0;
    } while (--iters > 0);
    (void)sink;
}
//#define GET_NANOTIME(t) (t.tv_sec * 1000000000LL + t.tv_nsec)
#define GET_NANOTIME(t) (t)
int get_cur_cpu_freq(int dev_idx, uint64_t* val) {
    //struct timespec t0,t1,t00,t01;
    //clock_gettime(CLOCK_REALTIME,&t00);
    //clock_gettime(CLOCK_REALTIME,&t0);
    int64_t t0,t1,t00;
    t00 = nanos();
    t0 = nanos();
    busy_loop(CURFREQ_EST_INTERVAL);
    t1 = nanos();
    //clock_gettime(CLOCK_REALTIME,&t1);
    // nano sec
    uint64_t otime = GET_NANOTIME(t0) - GET_NANOTIME(t00);
    uint64_t mtime = GET_NANOTIME(t1) - GET_NANOTIME(t0);
    // estimated frequency
    *val = CURFREQ_EST_INTERVAL*10000000LL / (mtime-otime); // scale the freq to the same as scaling interface
    printf("Time = %ld, INTERVAL=%ld, Time Overhead=%ld freq=%ld\n",mtime,,CURFREQ_EST_INTERVAL,otime,*val);
    return 0;
}
#else
int get_cur_cpu_freq(int dev_idx, uint64_t* val) {
    char buff[255]={0};
    char *endp;
    READ_CHECK_CPUFREQ(cur_freq_fd, buff, 255);
    *val = strtoul(buff, &endp, 0);
    return 0;
}
#endif

#if defined(__i386__)
static __inline__ unsigned long long rdtsc(void) {
    unsigned long long int x;
    __asm__ volatile (".byte 0x0f, 0x31" : "=A" (x));
    return x;
}
#elif defined(__x86_64__)
static __inline__ unsigned long long rdtsc(void) {
    unsigned hi, lo;
    __asm__ __volatile__ ("rdtsc" : "=a"(lo), "=d"(hi));
    return ( (unsigned long long)lo)|( ((unsigned long long)hi)<<32 );
}
#else
#error Unknown machine
#endif

#define TEST_ITER 500
#define RES_FN "dfvs-latency.csv"

#define MAX_UNCORE_VALUE 6425
#define MAX_UNCORE_FREQ  2.5
#define MIN_UNCORE_VALUE 4626
#define MIN_UNCORE_FREQ  1.8

#define GET_NANOTIME(t) (t.tv_sec * 1000000000LL + t.tv_nsec)

double get_cur_uncore_freq() {
    // read msr
    uint64_t uclk_b, uclk_e;
    read_msr_by_idx(0,U_MSR_PMON_FIXED_CTR,&uclk_b);
    usleep(EST_TIME_US);
    read_msr_by_idx(0,U_MSR_PMON_FIXED_CTR,&uclk_e);
    return ((double)(uclk_e-uclk_b))/(double)EST_TIME_S/1e9;
}

int main() {
    PAETT_init();
    init_msr();
    snprintf(cur_freq_filename, FILENAME_SIZE, "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq", 0);
    cur_freq_fd = open(cur_freq_filename, O_RDONLY);
    CHECK_VALID_FD(cur_freq_fd,"Failed to open scaling cur freq!\n");
    // enable uncore clk
    uint64_t en, uclk_b, uclk_e;
    read_msr_by_idx(0,U_MSR_PMON_FIXED_CTL,&en);
    write_msr_by_idx(0, U_MSR_PMON_FIXED_CTL, (en|UNCORE_CLK_MASK));
    // current state
    uint64_t cf, cft;
    double ucf = get_cur_uncore_freq();
    get_cur_cpu_freq(0, &cf);
    printf("Cur Core Freq: %.2lf GHz, Uncore Freq: %.2lf GHz\n", (double)cf/(double)1e6, ucf);
    write_msr_by_idx(0, U_MSR_PMON_FIXED_CTL, (en));
    fin_msr();
    PAETT_finalize();
}