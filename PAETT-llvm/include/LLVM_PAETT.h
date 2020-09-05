#ifndef _LLVM_PAETT_H_
#define _LLVM_PAETT_H_
namespace llvm {

Pass* createInstByPerfPass();
Pass* createFreqModPass(std::string PAETTFreqCommFn="paett_model.cache");
void initializeInstrmentByPerfPassPass(PassRegistry &Registry);
void initializeFreqModPassPass(PassRegistry &Registry);

}
#endif