/**************************************************
 * Wrapper functions of pthread library to capture
 * thread creation and destroy for PAETT's cpu binding 
 * and frequency tuning.
 * ***********************************************/
#include <pthread.h>
#include <dlfcn.h>
#include <freqmod.h>
#include <freqmod_API.h>

#ifndef _GNU_SOURCE
  #define _GNU_SOURCE
  #include <sched.h>
  #undef _GNU_SOURCE
#else
  #include <sched.h>
#endif

int __get_mydie(int cpu_num) {
    return cpu_num / (PAETT_get_ncpu()/PAETT_get_ndie());
}

int __cpu_bind_to(int cpu_num) {
    cpu_set_t mask;
    CPU_ZERO( &mask );
    CPU_SET( cpu_num, &mask );
    if( sched_setaffinity( 0, sizeof(mask), &mask ) == -1 ){
        printf("WARNING: Could not set CPU Affinity, continuing...\n");
    }
    return cpu_num;
}

extern uint64_t thread_core_config;
extern uint64_t thread_uncore_config;

int (*pthread_create_orig)(pthread_t *, const pthread_attr_t *, void *(*) (void *), void *);

struct wrapper_args_t {
    void *(*start_routine) (void *);
    void *arg;
    uint64_t core;
    uint64_t uncore;
};

void* __routine_wrapper(void* arg) {
    // cpu binding
    int __cpu = pthread_self() % PAETT_get_ncpu();
    __cpu_bind_to(__cpu);
    // frequency modification
    wrapper_args_t* wrapper_arg = (wrapper_args_t*)arg;
    PAETT_modCoreFreq(__cpu, wrapper_arg->core);
    wrapper_arg->start_routine(wrapper_arg->arg);
    PAETT_modCoreFreq(__cpu, MIN_CORE_VALIE);
    free(arg);
}

int pthread_create(pthread_t *thread, const pthread_attr_t *attr,
                          void *(*start_routine) (void *), void *arg) 
{
    if (!pthread_create_orig)
           pthread_create_orig = dlsym(RTLD_NEXT, "pthread_create");
    wrapper_args_t* wrap_arg = (wrapper_args_t*)malloc(sizeof(wrapper_args_t));
    wrap_arg->start_routine = start_routine;
    wrap_arg->arg = arg;
    wrap_arg->core = thread_core_config;
    wrap_arg->uncore = thread_uncore_config;
    return pthread_create_orig(thread, attr, __routine_wrapper, (void*)wrap_arg);
}


