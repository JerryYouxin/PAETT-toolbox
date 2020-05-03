# Prerequests

Before building PAETT tools, install several dependance listed below:

- C/C++ Compilers: gcc/g++
- x86_adapt
- x86_energy
- PAPI

# Build

PAETT libraries and tool applications can be built by make tools as follows.

~~~
$ cd PAETT-tool
$ make
~~~

The compiled executable tools are in `bin` directory, and libraries are in `lib` directory. 

# Usage

Compile the code with PAETT's clang/flang. We provide some wrapper scripts in `scripts` directory, where `paett-inst-flang`/`paett-inst-clang` is wrapper for PAETT's profiling instrumentation, and `paett-opt-flang`/`paett-opt-clang` is wrapper for PAETT's energy efficiency optimization.

To configure the profiling events of PAETT profiling, create/modify `profile.event` file in your executing path, all available PAPI events and energy collection `ENERGY` event (which utilizes x86_energy to collect energy profile for each region) can be configured. The generated profile can then be used to generate frequency commands by `freqcomm_gen` or list profiled CCT and significant regions by `paett_read_profile`.