if(WIN32 OR CYGWIN)
  set(LLVM_LINK_COMPONENTS Core Support)
endif()

#add_llvm_library( LLVMPAETT MODULE
add_llvm_library( LLVMPAETT
  LLVM_PAETT_instrument.cpp
  LLVM_PAETT_freqmod.cpp
  LLVM_PAETT_util.cpp

  DEPENDS
  intrinsics_gen
  )
