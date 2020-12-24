# Powerspector instrumentation passes for profiling/optimization

## Environment set up (Using environment module)

### Pre-requests

To install Powerspector, we need the following dependancies:

- environment module
- gcc (>=7)
- clang/flang with Powerspector-specific arguments (zip file in Release)

Specifically, the environment module can be installed with `yum`:

```
# yum install environment-modules 
```

### build

To build LLVM utilities with Powerspector augmented clang/flang compilers, please unzip the clang/flang package and install with our script:

```
# sh build-clang.sh # for clang
# sh build-flang.sh # for flang
```

The `clang` will be installed into `~/PAETT-llvm-install` by default, and the `flang` will be installed into `/path/to/this/repo/PAETT-llvm/flang-paett/install`

To modify the default installation path, please modify the path in installation script (`make.sh` for clang, `build.sh` for flang) after unzipping.

### Adding Environment modules

For environment modules of `flang` installation, save the following lines replacing the `/path/to/flang/install` to the path of the flang installation path, and place the module file as `/etc/modulefiles/flang`

```
#%Module1.0###################################################
## 
## flang (llvm 7.0.0 with Powerspector passes) modulefile
### 
set          topdir             /path/to/flang/install
prepend-path PATH               ${topdir}/bin
prepend-path LD_LIBRARY_PATH    ${topdir}/lib
prepend-path MANPATH            ${topdir}/man
prepend-path CPLUS_INCLUDE_PATH ${topdir}/include
prepend-path C_INCLUDE_PATH     ${topdir}/include
```

For environment modules of `clang` installation, save the following lines replacing the `/path/to/clang/install` to the path of the clang installation path, and place the module file as `/etc/modulefiles/clang`

```
#%Module1.0###################################################
## 
## clang (llvm 9.0.1 with Powerspector passes) modulefile
### 
set          topdir             /path/to/clang/install
prepend-path PATH               ${topdir}/bin
prepend-path LD_LIBRARY_PATH    ${topdir}/lib
prepend-path MANPATH            ${topdir}/man
prepend-path CPLUS_INCLUDE_PATH ${topdir}/include
prepend-path C_INCLUDE_PATH     ${topdir}/include
```

### Using flang/clang

Note that `flang` and `clang` is not recommended to use simultaneously as they will conflict with each other (specifically, the `clang` compiler will conflict with `clang-7` and `clang-9`).

```
# module load flang # load flang
# module rm flang # unload flang
# module load clang # load clang
# module rm clang # unload clang
```