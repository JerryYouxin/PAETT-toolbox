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
#ifdef MULTI_THREAD
#include <sys/syscall.h> 
#define MAX_THREAD 50
static int pid = 0;
#define INIT_MULTI_THREAD_VAR pid=syscall(__NR_gettid)
#define GET_THREADID PAPI_thread_id()
#ifdef USE_PTHREAD
    #define THREAD_HANDLER pthread_self
    #define GET_ACTIVE_THREAD_NUM 1
#elif USE_OPENMP
    #include <omp.h>
    #define THREAD_HANDLER omp_get_thread_num
    #define GET_ACTIVE_THREAD_NUM std::max(omp_get_max_threads(),1)
#else
    #error "Only USE_PTHREAD or USE_OPENMP is supportted!"
#endif
#else
#define MAX_THREAD 1
#define GET_THREADID 0
#define GET_ACTIVE_THREAD_NUM 1
#endif
static CallingContextLog root[MAX_THREAD];
static CallingContextLog* cur[MAX_THREAD] = {0};
static bool danger[MAX_THREAD] = {false};
#ifdef MULTI_THREAD
static int* _eventList;
#endif
// PAPI global vars
static uint8_t initialized = 0;
static int EventSet = PAPI_NULL;
static int eventNum = 0;
uint64_t elapsed_us;
uint64_t elapsed_cyc;

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

// C-style interfaces for lib call
extern "C" void PAETT_print();
extern "C" void PAETT_inst_init(int n, void* pe_list);
extern "C" void PAETT_inst_enter(uint64_t key); // key = MAKE_KEY(mid, l_key)
extern "C" void PAETT_inst_exit(uint64_t key);
#ifdef MULTI_THREAD
extern "C" void PAETT_inst_thread_init(uint64_t key); // key = MAKE_KEY(mid, l_key)
extern "C" void PAETT_inst_thread_fini(uint64_t key);
#endif
extern "C" void PAETT_inst_finalize();

// Debug logging
#define LIBPAETT_INST_LOGFN "libpaett_inst.log"
static FILE* LOG;

//#define DISABLE_PAPI_SAMPLING
#ifdef DISABLE_PAPI_SAMPLING
#include "energy_utils.h"
#endif

#define COUNT_FN ".paett_collect.cnt"
#define METRIC_FN "metric.out"
#define MAX_PMC_NUM 4

void PAETT_print() {
#ifndef DISABLE_PAPI_SAMPLING
    printf("\n=========== USING PAPI & Instrumentation =============\n");
#else
    printf("\n============ ONLY USING Instrumentation ==============\n");
#endif
#ifdef MULTI_THREAD
    printf("========== Multi Thread Support Enabled!! ============\n");
#else
    printf("========= Multi Thread Support Disabled!! ============\n");
#endif
}

//static BackTrace bt;
extern "C" bool contain_libcall(void* context, const char* file);

static void handler(int EventSet, void *address, long_long overflow_vector, void *context)
{
    int tid = GET_THREADID;
    if(danger[tid]) {
        //printf("WARNING!!!\n");
        // Drop this sample
        fprintf(LOG, "INFO: backtrace contain instrumentation library call. Drop this sample.\n");
        //fprintBackTrace(LOG, bt);
        assert(cur[0]);
        return ;
    }
    assert(overflow_vector!=0);
    int i=0, t;
    while(overflow_vector^0x1) {
        overflow_vector = overflow_vector >> 1; ++i;
    }
    assert(i<eventNum);
    assert(cur[tid]);
    ++total[i][tid];
    cur[tid]->data.eventData[i]+=THRESHOLD;
}

static std::vector<std::string> ename;
int es, ee;

static const char* _pre_ename[MAXEVENT] = {
    "PAPI_BR_NTK",
    "PAPI_LD_INS",
    "PAPI_L2_ICR",
    "PAPI_BR_MSP", // PEBS
    "PAPI_RES_STL",
    "PAPI_SR_INS", // PEBS
    "PAPI_L2_DCR" // PEBS
};
static int _pre_esize = 7;

std::string profile_path;

void PAETT_inst_init(int n, void* pe_list) {
    if(initialized) {
        fprintf(stderr, "Error Duplicated initialization!!!\n");
        exit(EXIT_FAILURE);
    }
    LOG = fopen(LIBPAETT_INST_LOGFN,"w");
#ifdef MULTI_THREAD
    INIT_MULTI_THREAD_VAR;
    // printf("Multi Thread Support Not Implemented !!!\n");
    // exit(EXIT_FAILURE);
#endif
    FILE* efile = fopen("profile.event","r");
    if(efile==NULL) {
        printf("INFO: profile.event not found for profiling! Use predefined event set.\n");
        int i;
        for(i=0;i<_pre_esize;++i) {
            ename.push_back(std::string(_pre_ename[i]));
        }
    } else {
        char en[50];
        while(EOF!=fscanf(efile, "%s", en)) {
            ename.push_back(std::string(en));
        }
        fclose(efile);
    }
    // PROFILE PATH
    char* envPath = getenv("PAETT_OUTPUT_PATH");
    if(envPath) {
        profile_path = std::string(envPath);
    } else {
        profile_path = std::string("./");
    }
    // other settings
    eventNum=ename.size(); n=eventNum;
    int* eventList = (int*)malloc(sizeof(int)*eventNum);
#ifdef MULTI_THREAD
    _eventList = eventList;
#endif
    if(n<=0) return ; // no perf event encountered
    initialized = 1; //eventNum=n;
    es=0, ee=n;
    if(n>MAX_PMC_NUM) {
        int nn;
        FILE* fp = fopen(COUNT_FN, "r");
        if(fp==NULL || fscanf(fp, "%d", &nn)==EOF) {
            nn = 0;
        } else fclose(fp);
        es = nn*MAX_PMC_NUM;
        ee = std::min(nn*MAX_PMC_NUM+MAX_PMC_NUM, n);
        assert(es<n);
        fp = fopen(COUNT_FN, "w");
        fprintf(fp, "%d", nn+1);
        fclose(fp);
        printf("Adding Event from %d to %d as event num too large (>%d). You may need multiple run to collect all data\n", es, ee, MAX_PMC_NUM);
        n = ee - es;
    }
    eventNum = n;
    // typically, backtrace size is often very small, so preallocate it.
    //bt.reserve(16);
    int retval, i;
    for(i=0;i<MAX_THREAD;++i) {
        cur[i]=&root[i];
        cur[i]->data.size = eventNum;
        cur[i]->data.eventData = (uint64_t*)malloc(sizeof(uint64_t)*eventNum);
        memset(cur[i]->data.eventData, 0, sizeof(uint64_t)*eventNum);
    }
    // int* eventList = (int*)pe_list;
    /* Initialize the PAPI library */
    CHECK_PAPI(PAPI_library_init(PAPI_VER_CURRENT), PAPI_VER_CURRENT);
#ifdef MULTI_THREAD
    CHECK_PAPI_ISOK(PAPI_thread_init(THREAD_HANDLER));
#endif
    assert(GET_THREADID==0);
#ifndef DISABLE_PAPI_SAMPLING
#ifdef MULTI_THREAD
    // cache event lists for parallel case
    //_eventList = (int*)malloc(sizeof(int)*n);
    //memcpy(_eventList, eventList, sizeof(int)*n);
#endif
    // check for available counters
    int numCounter = PAPI_num_counters();
    printf("NumCounter: %d, Will Add %d Events\n",numCounter, n);
    /* Create the EventSet */
    CHECK_PAPI_ISOK(PAPI_create_eventset(&EventSet));
    printf("EventSet: %d\n", EventSet);
    /* Add Events to our created EventSet */
    for(i=es;i<ee;++i) {
        //CHECK_PAPI_ISOK(PAPI_event_code_to_name(eventList[i], ename));
        CHECK_PAPI_ISOK(PAPI_event_name_to_code(ename[i].c_str(), &eventList[i]));
        printf("Add Event: [%lx]", eventList[i]); 
        printf("%s\n", ename[i].c_str());
        CHECK_PAPI_ISOK(PAPI_add_event(EventSet, eventList[i]));
        /* Call handler every xxx instructions */
        CHECK_PAPI_ISOK(PAPI_overflow(EventSet, eventList[i], THRESHOLD, 0, handler));
    }
#endif
    /* Add cycle event for measuring time distribution */
    // CHECK_PAPI_ISOK(PAPI_add_event(EventSet, PAPI_TOT_CYC));
    // CHECK_PAPI_ISOK(PAPI_overflow(EventSet, PAPI_TOT_CYC, THRESHOLD, 0, handler));
    danger[0]=false;
    /* Start counting */
    elapsed_us = PAPI_get_real_usec();
	elapsed_cyc = PAPI_get_real_cyc();
#ifndef DISABLE_PAPI_SAMPLING
    CHECK_PAPI_ISOK(PAPI_start(EventSet));
#else
    energy_init();
#endif
    ++(cur[0]->data.ncall);
    g_cycles[0] = PAPI_get_real_cyc();
}
#ifdef MULTI_THREAD
// actually should be inserted after PAETT_inst_enter
void PAETT_inst_thread_init(uint64_t key) {
    int retval, i;
    CHECK_PAPI_ISOK(PAPI_stop(EventSet, counterVal));
    //printf("...Thread init %lx\n",key);
    int tid = GET_THREADID;
    danger[tid] = true;
    assert(tid<=MAX_THREAD && "Thread number exceeds preallocated size!!!");
    // we should have already called PAETT_inst_enter
    assert(cur[tid] && cur[tid]->key==key);
    // Stop counting first to disable overflow
    cur[tid]->data.active_thread = std::max(cur[tid]->data.active_thread, (uint64_t)GET_ACTIVE_THREAD_NUM);
    for(i=es;i<ee;++i) {
        /* disable overflow handling for parallel regions, Instead, we directly use PMU counter value as we will not instrument any samples in parallel region */
        CHECK_PAPI_ISOK(PAPI_overflow(EventSet, _eventList[i], 0 /*disable*/, 0, handler));
    }
    // reset for counting events for the parallel region
    CHECK_PAPI_ISOK(PAPI_reset(EventSet));
    CHECK_PAPI_ISOK(PAPI_start(EventSet));
    //danger[tid] = false;
    begin_us_multi[tid] = PAPI_get_real_usec();
    g_cycles[tid] = PAPI_get_real_cyc();
}
// Different from init, the fini instrumentation will do the work similiarly as PAETT_inst_exit, so only fini should be inserted.
void PAETT_inst_thread_fini(uint64_t key) {
    int retval, i;
    uint64_t e_cycles = PAPI_get_real_cyc();
    uint64_t e_us = PAPI_get_real_usec();
    CHECK_PAPI_ISOK(PAPI_stop(EventSet, counterVal));
    //printf("...Thread fini %lx\n",key);
    int tid = GET_THREADID;
    //danger[tid] = true;
    assert(danger[tid]);
    elapsed_us_multi[tid] += e_us - begin_us_multi[tid];
    // make sure that init called before fini and the parallel region should not change the cursol
    if(cur[tid]->key==key) {
        cur[tid]->data.cycle += e_cycles - g_cycles[tid];
        //printf("[%lx]: ",key);
        for(i=0;i<cur[tid]->data.size;++i) {
            // normalized to THRESHOLD to make sure the same scale as other sampled regions
            // printf("%lu ",counterVal[i]);
            //cur[tid]->data.eventData[i] += counterVal[i] / THRESHOLD;
            cur[tid]->data.eventData[i] += counterVal[i];
        }
        //printf("/ %lu: ",THRESHOLD);
        //cur[tid]->data.print();
        //printf("\n");
        assert(cur[tid]!=&root[tid]);
        assert(cur[tid]->parent);
        cur[tid] = cur[tid]->parent;
    } else {
        printf("Error: [libpaett_inst] paett_inst_thread_fini not handled as key (cur=%lu, key=%lu) is not same !!!\n",cur[tid]->key, key);
        exit(-1);
    }
    /* enable overflow handling again as we exit the parallel region */
    for(i=es;i<ee;++i) {
        CHECK_PAPI_ISOK(PAPI_overflow(EventSet, _eventList[i], THRESHOLD /*enable*/, 0, handler));
    }
    CHECK_PAPI_ISOK(PAPI_reset(EventSet));
    CHECK_PAPI_ISOK(PAPI_start(EventSet));
    danger[tid] = false;
    g_cycles[tid] = PAPI_get_real_cyc();
}
#endif
void PAETT_inst_enter(uint64_t key) {
    if(danger[0] || !initialized) return;
    uint64_t e_cycles = PAPI_get_real_cyc();
    int tid = GET_THREADID;
    danger[tid] = true;
    // printf("...Enter %lx from %lx: (%lu) %lu <- %lu\n",key, cur[tid]->key, e_cycles - g_cycles[tid], e_cycles, g_cycles[tid]);
#ifdef DISABLE_PAPI_SAMPLING
    halt_energy_collection();
    cur[tid]->data.pkg_energy+= get_pkg_energy();
    cur[tid]->data.pp0_energy+= get_pp0_energy();
#endif
    //printf("cur=%p\n",cur[tid]);
    assert(cur[tid]);
    cur[tid]->data.cycle += e_cycles - g_cycles[tid];
    assert(cur[tid]!=NULL);
    cur[tid] = cur[tid]->getOrInsertChild(key);
    ++(cur[tid]->data.ncall);
    if(cur[tid]->data.eventData==NULL) {
        cur[tid]->data.active_thread = 1;
        cur[tid]->data.size = eventNum;
        cur[tid]->data.eventData = (uint64_t*)malloc(sizeof(uint64_t)*eventNum);
        memset(cur[tid]->data.eventData, 0, sizeof(uint64_t)*eventNum);
    }
#ifdef DISABLE_PAPI_SAMPLING
    restart_energy_collection();
#endif
    assert(cur[tid]);
    danger[tid] = false;
    //printf("ENTER...%lu\n",key);
    g_cycles[tid] = PAPI_get_real_cyc();
}

void PAETT_inst_exit(uint64_t key) {
    if(danger[0] || !initialized) return;
    uint64_t e_cycles = PAPI_get_real_cyc();
    int tid = GET_THREADID;
    danger[tid] = true;
    //printf("EXIT...%lu\n",key);
#ifdef DISABLE_PAPI_SAMPLING
    halt_energy_collection();
    cur[tid]->data.pkg_energy+= get_pkg_energy();
    cur[tid]->data.pp0_energy+= get_pp0_energy();
#endif
    assert(cur[tid]);
    if(cur[tid]->key==key) {
        //printf("...Exit %lx\n",key);
        cur[tid]->data.cycle += e_cycles - g_cycles[tid];
        assert(cur[tid]!=&root[tid]);
        assert(cur[tid]->parent);
        cur[tid] = cur[tid]->parent;
    } else {
        // printf("Warning: [libpaett_inst] paett_inst_exit not handled as key (cur=%lu, key=%lu) is not same !!!\n",cur[tid]->key, key);
    }
#ifdef DISABLE_PAPI_SAMPLING
    restart_energy_collection();
#endif
    danger[tid] = false;
    g_cycles[tid] = PAPI_get_real_cyc();
}

void PAETT_inst_finalize() {
    // disable first
    int retval;
#ifndef DISABLE_PAPI_SAMPLING
    CHECK_PAPI_ISOK(PAPI_stop(EventSet, counterVal));
#else
    energy_finalize();
    printf("INFO : Energy unit: %lu\n", energy_unit[0]);
#endif
    uint64_t end_us = PAPI_get_real_usec();
    uint64_t end_cyc = PAPI_get_real_cyc();
    elapsed_us = end_us - elapsed_us;
	elapsed_cyc = end_cyc - elapsed_cyc;
    printf("INFO : Elasped us: %lu\n", elapsed_us);
    printf("INFO : Elasped cyc: %lu\n", elapsed_cyc);
#ifndef DISABLE_PAPI_SAMPLING
    int i,j,k;
    for(i=0;i<eventNum+1;++i) {
        uint64_t t = total[i][0];
        for(j=1;j<MAX_THREAD;++j) t+=total[i][j]; 
        printf("INFO : TOTAL Overflow Count[%d] = %d\n", i, t); fflush(stdout);
    }
    for(i=0;i<eventNum+1;++i) {
        printf("INFO : TOTAL Counter Value[%d] = %ld\n", i, counterVal[i]); fflush(stdout);
    }
#endif
    fclose(LOG);
    int tid;
    elapsed_us_multi[0] = elapsed_us;
    {
        FILE* fp = fopen(METRIC_FN, "r");
        if(fp!=NULL) {
            std::string buff = updateMetrics(fp, &root[0]);
            fclose(fp);
            fp = fopen(METRIC_FN, "r");
            updateCCTMetrics(fp, &root[0]);
            fclose(fp);
            fp = fopen(METRIC_FN, "w");
            fprintf(fp, "%s", buff.c_str());
            fclose(fp);
        } else {
            FILE* fp = fopen(METRIC_FN, "w");
            printMetrics(fp, &root[0]);
            fclose(fp);
        }
    }
    std::string gprof_fn = profile_path+std::string(PAETT_GENERAL_PROF_FN);
#ifdef MULTI_THREAD
    FILE* fp = fopen(gprof_fn.c_str(), "w");
    //fprintf(fp, "%ld", elapsed_us);
    for(tid=0;tid<MAX_THREAD;++tid) {
        // if the root is not initialized, next;
        if(root[tid].data.ncall==0) continue;
        printf("\n======== THREAD ID = %d, elasped time = %ld ==========\n",tid, elapsed_us_multi[tid]);
        fprintf(fp," %ld",elapsed_us_multi[tid]);
#else
    FILE* fp = fopen(gprof_fn.c_str(), "w");
    fprintf(fp, "%ld", elapsed_us);
    fclose(fp);
    tid=0;
#endif
    // ROOT data.nall should not be modified during execution
    assert(root[tid].data.ncall==1);
    // ROOT data.ncall should be set to 1 as the program is called once
    // root[tid].data.ncall = 1;
    assert(root[tid].data.eventData!=NULL);
    if(cur[tid]!=&root[tid]) {
        printf("Warning: [libpaett_inst] cur[%d] is not at root when paett_inst_finalize is called : ",tid);
        CallingContextLog* p = cur[0]->parent;
        printf("cur=[%lu] ",cur[0]->key); 
        while(p!=NULL) { printf("<= [%lu] ",p->key); p=p->parent; }
        printf("\n");
    }
    // CallingContextLog::print(&root[0]);
#ifdef VERBOSE_DISTRIBUTION
    printDistribution(&root[tid], elapsed_us_multi[tid]);
#endif
    std::string prof_fn = profile_path+std::string(PAETT_PERF_INSTPROF_FN)+"."+std::to_string(tid);
    CallingContextLog::fprint(prof_fn.c_str(), &root[0]);
#ifdef MULTI_THREAD
    }
    fclose(fp);
#endif
    printf("=== finish ===\n"); fflush(stdout);
    initialized = false;
}