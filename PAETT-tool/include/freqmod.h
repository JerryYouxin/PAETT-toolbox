#ifndef _FREQMOD_H_
#define _FREQMOD_H_ 
#include <stdint.h>
typedef struct MSR_UNCORE_RATIO_LIMIT_STRUCT
{
    uint64_t max:7;
    uint64_t rsv1:1;
    uint64_t min:7;
    uint64_t rsv2:49;
} MSR_UNCORE_RATIO_LIMIT_T;

inline uint64_t MAKE_UNCORE_VALUE_BY_FREQ(uint64_t freq) { 
    union{ MSR_UNCORE_RATIO_LIMIT_T u; uint64_t v; } ur; 
    ur.u.max=ur.u.min=freq; 
    ur.u.rsv1=ur.u.rsv2=0; 
    return ur.v; 
}

inline double DECODE_MAX_FREQ_FROM_UNCORE_VALUE(uint64_t uncore) {
    union{ MSR_UNCORE_RATIO_LIMIT_T u; uint64_t v; } ur;
    ur.v = uncore;
    return (double)ur.u.max / 10.0;
}

inline double DECODE_FREQ_FROM_CORE_VALUE(uint64_t core) {
    return (double)core / (double)1e6;
}

// Round to 1e5
inline uint64_t MAKE_CORE_VALUE_FROM_FREQ(double freq) {
    uint64_t core = (uint64_t)(freq*10);
    return (uint64_t)(core+((freq>((double)core/10.0))?1:0)) * 1e5;
}

#endif