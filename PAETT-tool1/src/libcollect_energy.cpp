#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <stdint.h>
#include <signal.h>
#include <papi.h>
#include <cassert>
#include <string.h>

#include "CallingContextTree.h"
#include "common.h"

#include <sys/time.h>

#include <sys/syscall.h> 
#define MAX_THREAD 50

#define GET_THREADID 0

#include <omp.h>
#define THREAD_HANDLER omp_get_thread_num
#define GET_ACTIVE_THREAD_NUM std::max(omp_get_max_threads(),1)

#define METRIC_FN "metric.out"

//#define STOP_WHEN_WARN
//#define ENABLE_INFO_LOG
#ifdef ENABLE_INFO_LOG
#define INFO(msg, ...) printf("INFO: "); printf(msg, ##__VA_ARGS__); fflush(stdout)
#else
#define INFO(msg, ...)
#endif

static CallingContextLog root[MAX_THREAD];
static CallingContextLog* cur[MAX_THREAD] = {0};
static bool danger[MAX_THREAD] = {false};
static int* _eventList;
// PAPI global vars
static uint8_t initialized = 0;
static int EventSet = PAPI_NULL;
static int eventNum = 0;
uint64_t elapsed_us;

uint64_t elapsed_us_multi[MAX_THREAD] = {0};
uint64_t begin_us_multi[MAX_THREAD];

#define CYCLE_THRESHOLD 1
#define THRESHOLD 100000
#ifdef DEBUG_PAPI
#define CHECK_PAPI(stmt, PASS) printf("%s:%d: Executing %s\n",__FILE__, __LINE__,#stmt); fflush(stdout); if((retval=stmt)!=PASS) handle_error(retval)
#else
#define CHECK_PAPI(stmt, PASS) if((retval=stmt)!=PASS) handle_error(retval)
#endif
#define CHECK_PAPI_ISOK(stmt) CHECK_PAPI(stmt, PAPI_OK)
#define handle_error(e) do { fprintf(stderr, "Error at %s:%d: %s\n",__FILE__, __LINE__, PAPI_strerror(e)); exit(1); } while(0)

#define MAXEVENT 64
static int total[MAXEVENT][MAX_THREAD] = {0};
static long long counterVal[MAXEVENT] = {0};
static uint64_t g_cycles[MAX_THREAD] = {0};

// fake interfaces same as libpaett_inst
// C-style interfaces for lib call
extern "C" void PAETT_print();
extern "C" void PAETT_inst_init();
extern "C" void PAETT_inst_enter(uint64_t key); // key = MAKE_KEY(mid, l_key)
extern "C" void PAETT_inst_exit(uint64_t key);
extern "C" void PAETT_inst_thread_init(uint64_t key); // key = MAKE_KEY(mid, l_key)
extern "C" void PAETT_inst_thread_fini(uint64_t key);
extern "C" void PAETT_inst_finalize();

static double init_energy;

#include "energy_utils.h"

void PAETT_print() {
    printf("\n=========== COLLECTING METRICS ENERGY =============\n");
    fflush(stdout);
}

void PAETT_inst_init() {
    // the args are not used. just fakes
    if(initialized) {
        fprintf(stderr, "Error Duplicated initialization!!!\n");
        exit(EXIT_FAILURE);
    }
    // LOG = fopen(LIBPAETT_INST_LOGFN,"w");
    initialized = 1; 
    // typically, backtrace size is often very small, so preallocate it.
    int retval, i;
    for(i=0;i<MAX_THREAD;++i) {
        cur[i]=&root[i];
    }
    ++(cur[0]->data.ncall);
    energy_init();
    init_energy = get_pkg_energy();
    cur[0]->data.last_energy = init_energy;
    g_cycles[0] = PAPI_get_real_usec();
    elapsed_us = g_cycles[0];
}
// actually should be inserted after PAETT_inst_enter
void PAETT_inst_thread_init(uint64_t key) {
    int retval, i;
    int tid = GET_THREADID;
    assert(tid<=MAX_THREAD && "Thread number exceeds preallocated size!!!");
    assert(cur[tid] && !danger[tid] && initialized);
    if(cur[tid]->key!=key) {
        PAETT_inst_enter(key);
        printf("After Enter: thread_init for 0x%lx @ 0x%lx\n",key,cur[tid]->key); fflush(stdout);
    }
    danger[tid] = true;
    // we should have already called PAETT_inst_enter
    assert(cur[tid] && cur[tid]->key==key);
    // Stop counting first to disable overflow
    cur[tid]->data.active_thread = std::max(cur[tid]->data.active_thread, (uint64_t)GET_ACTIVE_THREAD_NUM);
    cur[tid]->data.last_energy = get_pkg_energy();
    begin_us_multi[tid] = PAPI_get_real_usec();
    g_cycles[tid] = PAPI_get_real_usec();
}
// Different from init, the fini instrumentation will do the work similiarly as PAETT_inst_exit, so only fini should be inserted.
void PAETT_inst_thread_fini(uint64_t key) {
    int retval, i;
    uint64_t e_cycles = PAPI_get_real_usec();
    uint64_t e_us = PAPI_get_real_usec();
    double energy = get_pkg_energy();
    int tid = GET_THREADID;
    double e = energy - cur[tid]->data.last_energy;
    CallingContextLog* p = cur[tid];
    while(p!=NULL) {
        p->data.pkg_energy+= e;
        RLOG("Update %lx PKG energy to %.6lf (+%.6lf) J\n", p->key, p->data.pkg_energy, e);
        p = p->parent;
    }
    RLOG("Thread_fini: PAETT_inst_thread_fini: cur[tid]->data.pkg_energy=%.2lf\n",cur[tid]->data.pkg_energy);
    elapsed_us_multi[tid] += e_us - begin_us_multi[tid];
    // make sure that init called before fini and the parallel region should not change the cursol
    if(cur[tid]->key==key) {
        cur[tid]->data.cycle += e_cycles - g_cycles[tid];
        assert(cur[tid]!=&root[tid]);
        assert(cur[tid]->parent);
        cur[tid] = cur[tid]->parent;
    } else {
        printf("Error: [libpaett_inst] paett_inst_thread_fini not handled as key (cur=%lu, key=%lu) is not same !!!\n",cur[tid]->key, key);
        exit(-1);
    }
    cur[tid]->data.last_energy = get_pkg_energy();
    danger[tid] = false;
    g_cycles[tid] = PAPI_get_real_usec();
}

void PAETT_inst_enter(uint64_t key) {
    if(danger[0] || !initialized) return;
    uint64_t e_cycles = PAPI_get_real_usec();
    double energy = get_pkg_energy();
    int tid = GET_THREADID;
    assert(tid==0);
    danger[tid] = true;
    //halt_energy_collection();
    double e = energy - cur[tid]->data.last_energy;
    CallingContextLog* p = cur[tid];
    while(p!=NULL) {
        p->data.pkg_energy+= e;
        RLOG("Enter: Update %lx PKG energy to %.6lf (+%.6lf) J\n", p->key, p->data.pkg_energy, e);
        p = p->parent;
    }
    assert(cur[tid]);
    cur[tid]->data.cycle += e_cycles - g_cycles[tid];
    cur[tid] = cur[tid]->getOrInsertChild(key);
    ++(cur[tid]->data.ncall);
    cur[tid]->data.last_energy = get_pkg_energy();
    assert(cur[tid]);
    danger[tid] = false;
    g_cycles[tid] = PAPI_get_real_usec();
}

void PAETT_inst_exit(uint64_t key) {
    if(danger[0] || !initialized) return;
    uint64_t e_cycles = PAPI_get_real_usec();
    double energy = get_pkg_energy();
    int tid = GET_THREADID;
    danger[tid] = true;
    double e = energy - cur[tid]->data.last_energy;
    CallingContextLog* p = cur[tid];
    while(p!=NULL) {
        p->data.pkg_energy+= e;
        RLOG("Exit: Update %lx PKG energy to %.6lf (+%.6lf) J\n", p->key, p->data.pkg_energy, e);
        p = p->parent;
    }
    assert(cur[tid]);
    if(cur[tid]->key==key) {
        cur[tid]->data.cycle += e_cycles - g_cycles[tid];
        assert(cur[tid]!=&root[tid]);
        assert(cur[tid]->parent);
        cur[tid] = cur[tid]->parent;
    } else {
#ifdef ENABLE_INFO_LOG
        printf("Warning: [libpaett_inst] paett_inst_exit not handled as key (cur=0x%lx, key=0x%lx) is not same !!!\n",cur[tid]->key, key);
        cur[tid]->printStack();
        fflush(stdout);
#endif
        if (auto warn = cur[tid]->findStack(key)) {
            printf("Error: Something May wrong as this key appears as current context's parent:\n");
            warn->printStack();
            exit(-1);
        } else {
#ifdef STOP_WHEN_WARN
            assert("Warning detected. Stop.");   
#endif
        }
    }
    cur[tid]->data.last_energy = get_pkg_energy();
    danger[tid] = false;
    g_cycles[tid] = PAPI_get_real_usec();
}

void PAETT_inst_finalize() {
    // disable first
    int retval;
    double fini_energy = get_pkg_energy();
    energy_finalize();
    printf("INFO : total Energy: %lf J\n", fini_energy-init_energy);
    uint64_t end_us = PAPI_get_real_usec();
    elapsed_us = end_us - elapsed_us;
    printf("INFO : Elasped Time: %lf s\n", elapsed_us*1e-6);
    int i,j,k;
    assert(initialized);
    // fclose(LOG);
    int tid;
    elapsed_us_multi[0] = elapsed_us;
    FILE* fp = fopen(METRIC_FN, "w");
    //fprintf(fp, "%ld", elapsed_us);
    for(tid=0;tid<MAX_THREAD;++tid) {
        // if the root is not initialized, next;
        if(root[tid].data.ncall==0) continue;
        printf("\n======== THREAD ID = %d, elasped time = %ld ==========\n",tid, elapsed_us_multi[tid]);
        // fprintf(fp," %ld",elapsed_us_multi[tid]);
        // ROOT data.nall should not be modified during execution
        assert(root[tid].data.ncall==1);
        if(cur[tid]!=&root[tid]) {
            printf("Warning: [libpaett_inst] cur[%d] is not at root when paett_inst_finalize is called : ",tid);
            CallingContextLog* p = cur[0]->parent;
            printf("cur=[%lu] ",cur[0]->key); 
            while(p!=NULL) { printf("<= [%lu] ",p->key); p=p->parent; }
            printf("\n");
        }
        printMergedEnergy(fp, &root[tid]);
    }
    fclose(fp);
    printf("=== finish ===\n"); fflush(stdout);
    initialized = false;
}