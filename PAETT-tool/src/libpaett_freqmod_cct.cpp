#define LIBPAETT_CCT_FREQFILE "paett_freqmod.cct"
#ifndef USE_NAMESPACE
#include <freqmod.h>
#include "libpaett_freqmod.cpp"
#include "CCTFreqCommand.h"
// C-style interfaces for lib call
extern "C" void PAETT_print();
extern "C" void PAETT_inst_init();
extern "C" void PAETT_inst_enter(uint64_t key); // key = MAKE_KEY(mid, l_key)
extern "C" void PAETT_inst_exit(uint64_t key);
extern "C" void PAETT_inst_thread_init(uint64_t key); // key = MAKE_KEY(mid, l_key)
extern "C" void PAETT_inst_thread_fini(uint64_t key);
extern "C" void PAETT_inst_finalize();
#define FUNCNAME(func) func
#else
namespace freqmod_cct {
#include <freqmod.h>
#include "libpaett_freqmod.cpp"
#include "CCTFreqCommand.h"
#define FUNCNAME(func) __FREQMOD_CCT_##func
#endif

// ReadOnly frequency commands, so all threads share a single CCTFreqCommand
CCTFreqCommand* root=NULL;

/* fine-grained tuning: 
    1. utilize cpu binding to enable per-core tuning. 
    2. per-socket uncore tuning is tuned before entering parallel region
    3. only utilize spread cpu affinity in default (TODO: utilize affinity tuning with openmp legency, e.g. spread, scatter, etc.)
*/
#define ENABLE_FINEGRANED_TUNING
#ifdef ENABLE_FINEGRANED_TUNING
// TODO: implement cpu affinity and binding with hwloc library (for better portablity and abstraction)
// sched.h needs _GNU_SOURCE for glibc specific cpu affinity functions (sched_*)
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#include <sched.h>
#undef _GNU_SOURCE
#else
#include <sched.h>
#endif
#include <unistd.h>

#include <config.h>

#define INVALID_CPU -1

template<typename T>
inline T min(const T a,const T b) { return (a)<(b)?(a):(b); }

enum CPU_Affinity_t {
    DEFAULT=0, CLOSE, SPREAD, 
#ifdef ENABLE_ADAPTIVE
    ADAPTIVE
#endif
};

int __get_mydie(int cpu_num) {
    return cpu_num / (PAETT_get_ncpu()/PAETT_get_ndie());
}

// static cpu_set_t __mask;
// void __cache_original_affinity() {
//     if( sched_getaffinity( 0, sizeof(__mask), &__mask ) == -1 ){
//         printf("WARNING: Could not get CPU Affinity, continuing...\n");
//     }
// }

// void __restore_original_affinity() {
//     if( sched_setaffinity( 0, sizeof(__mask), &__mask ) == -1 ){
//         printf("WARNING: Could not set CPU Affinity, continuing...\n");
//     }
// }

void __tune_with_affinity(CPU_Affinity_t aff, uint64_t tnum, uint64_t core, uint64_t uncore) {
    // printf("-- Thread %d Tuning with affinity: core=%ld, uncore=%ld, tnum=%ld\n", omp_get_thread_num(), core, uncore, tnum);
    assert(tnum>=0 && tnum<=NCPU);
    uint64_t step;
    switch(aff) {
        case CLOSE:
            for(uint64_t i=0;i<tnum;++i) {
                PAETT_modCoreFreq(i,core);
            }
            for(uint64_t i=tnum;i<PAETT_get_ncpu();++i) {
                PAETT_modCoreFreq(i,MIN_CORE_VALIE);
            }
            step = PAETT_get_ncpu() / PAETT_get_ndie();
            for(uint64_t i=0, k=0;i<tnum;i+=step, ++k) {
                // printf("[DEBUG] TUNE WITH AFFINITY: %ld uncore to %ld\n",k, uncore);
                PAETT_modUncoreFreq(k,uncore);
            }
            // printf("step=%ld, i start=%d, ndie=%ld\n",step,__get_mydie(tnum-1)+1,PAETT_get_ndie());
            for(uint64_t i=__get_mydie(tnum-1)+1;i<PAETT_get_ndie();++i) {
                // printf("[DEBUG] TUNE WITH AFFINITY: %ld uncore to %ld\n",i, MIN_UNCORE_VALIE);
                PAETT_modUncoreFreq(i,MIN_UNCORE_VALIE);
            }
            break;
        case SPREAD:
            uint64_t dies = min(tnum, PAETT_get_ndie());
            uint64_t corePerDie = PAETT_get_ncpu() / PAETT_get_ndie();
            uint64_t tnumPerDie = tnum / PAETT_get_ndie();
            for(uint64_t i=0;i<tnum && i<PAETT_get_ndie(); ++i) {
                uint64_t js=i*corePerDie;
                uint64_t je=js+tnumPerDie;
                uint64_t jr=js+corePerDie;
                for(uint64_t j=js;j<je;++j) {
                    PAETT_modCoreFreq(j,core);
                }
                for(uint64_t j=je;j<jr;++j) {
                    PAETT_modCoreFreq(j, MIN_CORE_VALIE);
                }
                PAETT_modUncoreFreq(i,uncore);
            }
            for(uint64_t j=tnum*corePerDie;j<PAETT_get_ncpu();++j) {
                PAETT_modCoreFreq(j, MIN_CORE_VALIE);
            }
            for(uint64_t i=tnum;i<PAETT_get_ndie();++i) {
                PAETT_modUncoreFreq(i,MIN_CORE_VALIE);
            }
            break;
#ifdef ENABLE_ADAPTIVE
        case ADAPTIVE:
            cpu_set_t *set;
            pid_t tid;
            tid = syscall(SYS_gettid);
            set = CPU_ALLOC(available_cores);
            size_t set_size = CPU_ALLOC_SIZE(available_cores);
            if (set == NULL) {
                printf("ERROR during tuning with affinity: CPU_ALLOC\n");
                return;
            }
            CPU_ZERO_S(set_size, set);
            int err = sched_getaffinity(tid, set_size, set);
            if (err == -1) {
                printf("ERROR when getting affinity: sched_getaffinity\n");
                return ;
            }
            uint64_t uncoreSet = 0;
            for(uint64_t i=0;i<PAETT_get_ncpu();++i) {
                if (CPU_ISSET_S(i, set_size, set)) {
                    PAETT_modCoreFreq(i, core);
                    die = __get_mydie(i);
                    if(die!=0) uncoreSet |= (1<<die);
                    else       uncoreSet |= 1;
                } else {
                    PAETT_modCoreFreq(i, MIN_CORE_VALIE);
                }
            }
            for(uint64_t i=0;i<PAETT_get_ndie();++i) {
                if(uncoreSet & (1<<i)) PAETT_modUncoreFreq(i, uncore);
                else                   PAETT_modUncoreFreq(i, MIN_CORE_VALIE);
            }
            break;
#endif
        default:
            PAETT_modCoreFreqAll(core);
            PAETT_modUncoreFreqAll(uncore);
            break;
    }
}

static thread_local int __cpu=INVALID_CPU;
static thread_local int __die=INVALID_CPU;

// int __cpu_bind_to_range(int cpu_beg, int cpu_end) {
//     cpu_set_t mask;
//     CPU_ZERO( &mask );
//     for(int i=cpu_beg;i<=cpu_end;++i) {
//         CPU_SET( i, &mask );
//     }
//     if( sched_setaffinity( 0, sizeof(mask), &mask ) == -1 ){
//         printf("WARNING: Could not set CPU Affinity, continuing...\n");
//     }
//     return cpu_end-cpu_beg+1;
// }

// int __cpu_bind_to(int cpu_num) {
//     cpu_set_t mask;
//     CPU_ZERO( &mask );
//     CPU_SET( cpu_num, &mask );
//     if( sched_setaffinity( 0, sizeof(mask), &mask ) == -1 ){
//         printf("WARNING: Could not set CPU Affinity, continuing...\n");
//     }
//     return cpu_num;
// }

// // return binded cpu number
// int __cpu_bind_to_self() {
//     int cpu_num = sched_getcpu();
//     __cpu_bind_to(cpu_num);
//     return cpu_num;
// }

#endif

// Each thread has its own cct pointer 
// NOTE: Nested parallelization is not supported!
static thread_local CCTFreqCommand* cur=NULL;

uint64_t core_default = 0;
uint64_t uncore_default = 0;

int danger = 0;
FILE* FLOG;

void FUNCNAME(PAETT_print)() {
    printf("\n=========== USING PAETT CCT-AWARE FREQMOD ============\n");
}

#ifdef ENABLE_FINEGRANED_TUNING
CPU_Affinity_t affinity=CPU_Affinity_t::CLOSE;
inline void __tuneTo(CCTFreqCommand* self) {
    uint64_t core = core_default;
    uint64_t uncore = uncore_default;
    uint64_t thread = 0;
    if(self!=NULL) {
        if(self->data.core)   core = self->data.core;
        if(self->data.uncore) uncore = self->data.uncore;
        // printf("-- Thread %d Tuning with (thread=%d, core=%d, core=%d)\n", omp_get_thread_num(), self->data.thread, core, uncore);
        if(self->data.thread>1 && self->data.thread<=NCPU) {
            PAETT_modOMPThread(self->data.thread);
            __tune_with_affinity(affinity, self->data.thread, core, uncore);
            return ;
        } else if (self->data.thread==0 || self->data.thread>NCPU) {
            return;
        }
    }
    // printf("-- Thread %d Tuning with (thread=%d, core=%d, core=%d)\n", omp_get_thread_num(), omp_get_max_threads(), core, uncore); 
    __tune_with_affinity(affinity, omp_get_max_threads(), core, uncore);
}
#else
inline void __tuneTo(CCTFreqCommand* self) {
    if(self) {
        if(self->data.thread!=0) {
            PAETT_modOMPThread(self->data.thread);
        }
        PAETT_modCoreFreqAll(self->data.core);
        PAETT_modUncoreFreqAll(self->data.uncore);
    }
}
#endif

#include <limits.h>

enum STR2INT_ERROR { SUCCESS, OVERFLOW, UNDERFLOW, INCONVERTIBLE };

STR2INT_ERROR str2int (int &i, char const *s, int base = 0)
{
    char *end;
    long  l;
    errno = 0;
    l = strtol(s, &end, base);
    if ((errno == ERANGE && l == LONG_MAX) || l > INT_MAX) {
        return OVERFLOW;
    }
    if ((errno == ERANGE && l == LONG_MIN) || l < INT_MIN) {
        return UNDERFLOW;
    }
    if (*s == '\0' || *end != '\0') {
        return INCONVERTIBLE;
    }
    i = l;
    return SUCCESS;
}

void FUNCNAME(PAETT_inst_init)() {
    double s = omp_get_wtime();
    PAETT_init();
    double e = omp_get_wtime();
    printf("Init FREQMOD Time: %lf s\n", e-s);
    s = omp_get_wtime();
    char* envPath = getenv("PAETT_CCT_FREQUENCY_COMMAND_FILE");
    char* defaultCore = getenv("PAETT_DEFAULT_CORE_FREQ");
    char* defaultUncore = getenv("PAETT_DEFAULT_UNCORE_FREQ");
    if(envPath==NULL) {
        root = readCCTFreqCommand(LIBPAETT_CCT_FREQFILE);
    } else {
        root = readCCTFreqCommand(envPath);
    }
#ifdef ENABLE_FINEGRANED_TUNING
    char* affinitySetting = getenv("PAETT_AFFINITY");
    if(affinitySetting!=NULL) {
        std::string aff = std::string(affinitySetting);
        if(aff=="CLOSE") {
            affinity = CPU_Affinity_t::CLOSE;
        } else if (aff=="SPREAD") {
            affinity = CPU_Affinity_t::SPREAD;
        } else {
            affinity = CPU_Affinity_t::DEFAULT;
        }
    }
#endif
    e = omp_get_wtime();
    printf("Init READ Time: %lf s\n", e-s);
    s = omp_get_wtime();
    // if(root) {
    //     printf("[DEBUG] key=0x%lx, core=%ld, uncore=%ld, thread=%ld\n",root->key, root->data.core, root->data.uncore, root->data.thread); 
    //     root->printStack(); 
    // }
    if(defaultCore) { 
        int core;
        int ret = str2int(core, defaultCore);
        core_default = core;
        if(ret!=SUCCESS || core_default<MIN_CORE_FREQ || core_default>MAX_CORE_FREQ) {
            printf("Warning: PAETT_DEFAULT_CORE_FREQ is set to invalid value(%s)! It must be a integer value ranged from [%d,%d]!\n", defaultCore, MIN_CORE_FREQ, MAX_CORE_FREQ);
            printf("Warning: Ignore the default core frequency setting\n");
            core_default = 0;
        }
    }
    if(defaultUncore) { 
        int uncore;
        int ret = str2int(uncore, defaultUncore); 
        uncore_default = uncore;
        if(ret!=SUCCESS || uncore_default<MIN_UNCORE_FREQ || uncore_default>MAX_UNCORE_FREQ) {
            printf("Warning: PAETT_DEFAULT_UNCORE_FREQ is set to invalid value(%s)! It must be a integer value ranged from [%d,%d]!\n", defaultUncore, MIN_UNCORE_FREQ, MAX_UNCORE_FREQ);
            printf("Warning: Ignore the default core frequency setting\n");
            uncore_default = 0;
        }
    }
    core_default = MAKE_CORE_VALUE_FROM_FREQ(core_default/10.0);
    uncore_default = MAKE_UNCORE_VALUE_BY_FREQ(uncore_default);
    printf("-- [Info]: Default core=%d, uncore=%d\n", core_default, uncore_default);
    if(root) {
        printf("Configured Frequency Command CCT:\n");
        CCTFreqCommand::print(root);
        root->reset();
        __tuneTo(root);
    } else {
        printf("No frequency command CCT configuration found\n");
#ifdef ENABLE_FINEGRANED_TUNING
        printf("Use default settings provided: core=%ld, uncore=%ld\n", core_default, uncore_default);
        __tuneTo(NULL);
#endif
    }
    e = omp_get_wtime();
    printf("Init SET Time: %lf s\n", e-s);
    // FLOG = fopen("libpaett_freqmod_cct.log","w");
    // fprintf(FLOG, "libpaett_freqmod_cct initialized: %d\n", root!=NULL); fflush(FLOG);
}

void FUNCNAME(PAETT_inst_exit)(uint64_t key) {
    // fprintf(FLOG,"Exit %ld: danger=%d, root=%p\n", key, danger, root); fflush(FLOG);
// #ifdef ENABLE_FINEGRANED_TUNING
//     if(danger==1) {
//         uint64_t core = core_default;
//         uint64_t uncore = uncore_default;
//         if(root!=NULL) {
//             //printf("-- Thread %d Tuning core[%d]=%ld, uncore[%d]=%ld\n", __cpu, __cpu, root->data.core, __die, root->data.uncore);
//             if(root->data.core) core = MIN_CORE_VALIE;
//             if(root->data.uncore) uncore = MIN_UNCORE_VALIE;
//         }
//         PAETT_modCoreFreq(__cpu,core);
//         PAETT_modUncoreFreq(__die, uncore);
//     }
// #endif
    // printf("Thread %d Exit %d, danger=%d, cpu=%d\n", omp_get_thread_num(), key, danger, __cpu);
    if(danger || root==NULL) return;
    //printf("Exit key=%ld: thread %ld, core %ld, uncore %ld\n",key,root->data.thread, root->data.core, root->data.uncore);
    if(root->key==key) {
        root = root->parent;
        __tuneTo(root);
    }
}

void FUNCNAME(PAETT_inst_enter)(uint64_t key) {
    // fprintf(FLOG,"Enter %ld: danger=%d, root=%p\n", key, danger, root); fflush(FLOG);
// #ifdef ENABLE_FINEGRANED_TUNING
//     if(__cpu==INVALID_CPU) {
//         __cpu = omp_get_thread_num();
//         __die = __get_mydie(__cpu);
//         __cpu_bind_to(__cpu);
//         printf("Thread %d bind to cpu %d of socket %d\n",__cpu, __cpu, __die);
//         // if(__cpu==1 && root) { 
//         //     printf("[DEBUG] key=%ld, core=%ld, uncore=%ld, thread=%ld\n",key, root->data.core, root->data.uncore, root->data.thread); 
//         //     root->printStack(); 
//         // }
//     }
//     if(danger==1) {
//         uint64_t core = core_default;
//         uint64_t uncore = uncore_default;
//         if(root!=NULL) {
//             //printf("-- Thread %d Tuning core[%d]=%ld, uncore[%d]=%ld\n", __cpu, __cpu, root->data.core, __die, root->data.uncore);
//             if(root->data.core) core = root->data.core;
//             if(root->data.uncore) uncore = root->data.uncore;
//         }
//         printf("-- Thread %d Tuning with (core=%ld, uncore=%ld)\n", __cpu, core, uncore);
//         PAETT_modCoreFreq(__cpu,core);
//         PAETT_modUncoreFreq(__die, uncore);
//     }
// #endif
    // printf("Thread %d Enter %d, danger=%d, cpu=%d\n", omp_get_thread_num(), key, danger, __cpu);
    if(danger || root==NULL) return;
    //printf("BEFORE ENTER: CURRENT=%ld, (%ld %ld %ld), cur=%ld\n", root->key, root->data.core, root->data.uncore, root->data.thread, root->cur_index);
    root = root->getOrInsertChild(key);
    //printf("Enter key=%ld: thread %ld, core %ld, uncore %ld, cur=%ld, start=%ld, end=%ld\n",key,root->data.thread, root->data.core, root->data.uncore, root->cur_index, root->start_index, root->end_index);
    __tuneTo(root);
}

void FUNCNAME(PAETT_inst_thread_init)(uint64_t key) {
    //printf("[thread %d] THREAD_INIT...key=%ld\n",omp_get_thread_num(),key);
    // if(root) root->printStack();
#ifdef ENABLE_FINEGRANED_TUNING
    if(danger) return;
    printf("OMP thread configuration: %d\n", omp_get_max_threads());
    fflush(stdout);
    if(root) {
        // printf("key %lx, thread %ld, core %ld, uncore %ld\n", key, root->data.thread, root->data.core, root->data.uncore);
// #ifndef USE_NAMESPACE
        root = root->getOrInsertChild(key);
// #endif
        uint64_t core = core_default;
        uint64_t uncore = uncore_default;
        if(root->data.core) core = root->data.core;
        if(root->data.uncore) uncore = root->data.uncore;
        if(root->data.thread!=0) {
            PAETT_modOMPThread(root->data.thread);
            __tune_with_affinity(affinity, root->data.thread, core, uncore);
        } else {
            __tune_with_affinity(affinity, omp_get_max_threads(), core, uncore);
        }
        // PAETT_modCoreFreqAll(MIN_CORE_VALIE);
        // PAETT_modUncoreFreqAll(MIN_UNCORE_VALIE);
    } else {
        //__cpu_bind_to_range(0, tnum);
        //printf("%d\n", omp_get_max_threads());
        __tune_with_affinity(affinity, omp_get_max_threads(), core_default, uncore_default);
    }
#else
    FUNCNAME(PAETT_inst_enter)(key);
#endif
    ++danger;
}

void FUNCNAME(PAETT_inst_thread_fini)(uint64_t key) {
    --danger;
    //printf("[thread %d] THREAD_FINI...key=%ld\n",omp_get_thread_num(),key);
#ifdef ENABLE_FINEGRANED_TUNING
    if(danger) return;
    // if(root) {
    //     if(root->parent->key!=key) root = root->parent;
    //     if(root->data.thread!=0) {
    //         PAETT_modOMPThread(root->data.thread);
    //         //__cpu_bind_to_range(0, root->data.thread);
    //         // __tune_with_affinity(CPU_Affinity_t::CLOSE, root->data.thread, root->data.core, root->data.uncore);
    //     // } else {
    //     //     // must be a non-parallel region, so back to serial
    //     //     // __tune_with_affinity(CPU_Affinity_t::CLOSE, 1, root->data.core, root->data.uncore);
    //     }
    //     for(int i=0;i<ncpu;++i) {
    //         if(i!=__cpu) {
    //             //PAETT_modCoreFreq(i,MIN_CORE_VALIE);
    //             //PAETT_modUncoreFreq(i,MIN_UNCORE_VALIE);
    //         }
    //     }
    //     __tuneTo(root);
    // } else {
    //     for(int i=0;i<ncpu;++i) {
    //         if(i!=__cpu) {
    //             //PAETT_modCoreFreq(i,MIN_CORE_VALIE);
    //             //PAETT_modUncoreFreq(i,MIN_UNCORE_VALIE);
    //         }
    //     }
    //     PAETT_modCoreFreq(__cpu,core_default);
    //     PAETT_modUncoreFreq(__die, uncore_default);
    // }
#ifndef USE_NAMESPACE
    if(root) root = root->parent;
    __tuneTo(root);
#endif
#else
    FUNCNAME(PAETT_inst_exit)(key);
#endif
}

void FUNCNAME(PAETT_inst_finalize)() {
    if(root!=NULL) {
        root->clear();
        CCTFreqCommand::free(root);
        root = NULL;
    }
    PAETT_finalize();
    // fprintf(FLOG, "Finish\n"); fflush(FLOG);
    // fclose(FLOG);
}

#ifdef USE_NAMESPACE
}
#endif