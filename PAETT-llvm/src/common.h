#ifndef _COMMON_H_
#define _COMMON_H_
#define INFO_FN "instrmentByPerfPass.info"
#define PAETT_PERF_INSTPROF_FN "PAETT_PERF_INST.prof"
#define PAETT_GENERAL_PROF_FN "PAETT_GENERAL_INST.prof"
#define MAKE_THREAD_PROF_FN(BASE, TID) (std::string(BASE)+"."+std::to_string(TID)).c_str()
#define N_CPU 1
#define CHECK_WRITE(stmt, sz) do {if((r=stmt)!=sz) { fprintf(stderr, "Failed to write data into profile [%s:%d]: %ld should be written but %ld returned!\n",__FILE__, __LINE__,sz, r); exit(EXIT_FAILURE); }}while(0)
#define CHECK_READ(stmt, sz) do {if((r=stmt)!=sz) { fprintf(stderr, "Failed to read data from profile [%s:%d]: %ld should be read but %ld returned!\n",__FILE__,__LINE__,sz, r); exit(EXIT_FAILURE); }}while(0)
#define SAFE_WRITE(ptr, elesz, sz, fp) CHECK_WRITE(fwrite(ptr, elesz, sz, fp), sz)
#define SAFE_READ(ptr, elesz, sz, fp) CHECK_READ(fread(ptr, elesz, sz, fp), sz)

#define MAKE_KEY(a,b) ((a<<32)|(b&0xffffffff))
#define DECODE_FIRST(k) (k>>32)
#define DECODE_SECOND(k) (k&0xffffffff)

#define KEYMAP_FN "PAETT.keymap"

// flang only as it uses llvm 7.0.0
#define USE_OLD_LLVM
#define CCT_ROOT_KEY -1
#define CCT_INVALID_KEY ((uint64_t)-2)
#define CHECK_THRESHOLD 10
#endif
