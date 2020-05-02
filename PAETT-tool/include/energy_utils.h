#ifndef __ENERGY_UTILS_H__
#define __ENERGY_UTILS_H__
#include <stdint.h>
#include <stdio.h>

//#define ENABLE_DEBUG_LOG
#ifdef ENABLE_DEBUG_LOG
FILE* RAPL_LOG;
#define RAPL_LOG_FN "energy_utils.log"
#define RLOG_INIT do { RAPL_LOG = fopen(RAPL_LOG_FN, "a+"); if(!RAPL_LOG) printf("Error to open RAPL_LOG: %s\n", RAPL_LOG_FN); } while(0)
#define RLOG(msg, ...) if(RAPL_LOG) fprintf(RAPL_LOG, msg, ##__VA_ARGS__)
#define RLOG_FINI fclose(RAPL_LOG)
#else
#define RLOG_INIT 
#define RLOG(msg, ...) 
#define RLOG_FINI 
#endif

extern "C" {
#include <x86_energy.h>
}
/*******************************************************************************************
 * x86_energy can access intel_powerclamp, intel_rapl_perf, msr/msr-safe, x86_adapt et.al. *
 * The access delay of these interfaces tested in our local machine results as follows:    *
 * x86_adapt < msr/msr-safe < intel_rapl_perf < intel_powerclamp                           *
 * To minimize the energy profiling overhead, this wrapper will try to use the fastest     *
 * x86_adapt as energy counters and read energy values by x86_energy library API           *
 *******************************************************************************************/

#define MAX_COUNTER_NUM 10

static x86_energy_architecture_node_t* hw_root;
static struct x86_energy_access_source* energy_access_source=NULL;
static x86_energy_single_counter_t E_counter[X86_ENERGY_GRANULARITY_SIZE][MAX_COUNTER_NUM]={0};
static int E_counter_num[X86_ENERGY_GRANULARITY_SIZE] = {0};

inline int energy_init() {
    if(energy_access_source) return 0; // already initialized
    RLOG_INIT;
    RLOG("\n========= new run =======\n");
    hw_root = x86_energy_init_architecture_nodes();
    static x86_energy_mechanisms_t* a = x86_energy_get_avail_mechanism();
    if(a && a->name) {
        RLOG("Architecture: %s\n", a->name);
    } else {
    	printf(x86_energy_error_string());
    	return 1;
    }
    char target[] = "x86a-rapl";
    for (size_t i = 0; i < a->nr_avail_sources; i++)
    {
        RLOG("Testing source %s\n", a->avail_sources[i].name);
        if(strcmp(target, a->avail_sources[i].name)==0) {
            energy_access_source = &(a->avail_sources[i]);
            break;
        }
    }
    if(energy_access_source==NULL) {
        RLOG("Warning: %s not found. Try use other available interfaces\n",target);
        if(a->nr_avail_sources>0) {
            // the first one seems always the most general and slowest interface, so use the last one if x86_adapt is not found
            energy_access_source = &(a->avail_sources[a->nr_avail_sources-1]);
        } else {
            printf("Error: No other available interface found!\n");
            return 1;
        }
    }
    // now available energy access instance is referenced by energy_access_source
    int ret = energy_access_source->init();
    if(ret!=0) {
        RLOG("Init failed\n");
        return 1;
    }
    // setup counters
    for (int j = 0; j < X86_ENERGY_COUNTER_SIZE; j++)
    {
        if (a->source_granularities[j] >= X86_ENERGY_GRANULARITY_SIZE)
            continue;
#ifndef COLLECT_ALL
        // only collect pkg info
        if (j!=X86_ENERGY_COUNTER_PCKG)
            continue;
#endif
        RLOG("Try counter %d\n", j);
        for (int package = 0;
             package < x86_energy_arch_count(hw_root, a->source_granularities[j]); package++)
        {
            RLOG("avail for granularity %d. There are %d devices avail for this counter, "
                "testing %d\n",
                a->source_granularities[j],
                x86_energy_arch_count(hw_root, a->source_granularities[j]), package);
            E_counter[j][E_counter_num[j]] = energy_access_source->setup(j, package);
            if (E_counter[j][E_counter_num[j]] == NULL)
            {
                printf("Could not add counter %d for package\n", j);
                printf("%s", x86_energy_error_string());
                return 1;
            }
            ++E_counter_num[j];
        }
    }
}

inline double get_pkg_energy() {
    if(energy_access_source==NULL) return 0.0;
    double res = 0;
    for(int i=0;i<E_counter_num[X86_ENERGY_COUNTER_PCKG];++i) {
        res += energy_access_source->read(E_counter[X86_ENERGY_COUNTER_PCKG][i]);
    }
    RLOG("Reading PKG energy: %.2lf J\n", res);
    return res;
}

inline void energy_finalize() {
    if(energy_access_source) {
        for(int j=0;j<X86_ENERGY_GRANULARITY_SIZE;++j) {
            for(int i=0;i<E_counter_num[j];++i) {
                if(E_counter[j][i]!=0) {
                    energy_access_source->close(E_counter[j][i]);
                    E_counter[j][i]=NULL;
                }
            }
        }
        energy_access_source->fini();
        energy_access_source = NULL;
        x86_energy_free_architecture_nodes(hw_root);
        RLOG("============= Energy Finalized ==============\n");
        RLOG_FINI;
    }
}

#endif