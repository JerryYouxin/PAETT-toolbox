#include "llvm/Pass.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Function.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/IR/Type.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Instruction.h"
#include "llvm/ADT/ilist.h"
#include "llvm/IR/SymbolTableListTraits.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/DebugLoc.h"
#include "llvm/IR/GlobalValue.h"
#include "llvm/IR/Metadata.h"
#include "llvm/IR/Constants.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/Transforms/Utils/Cloning.h"
#include "llvm/Analysis/LoopInfo.h"
#include "llvm/IR/DebugInfoMetadata.h"
#include "llvm/IR/GlobalVariable.h"
#include "llvm/Transforms/Utils/LoopSimplify.h"
#include <iostream>
#include <fstream>
// PAETT headers
// #include "LLVM_PAETT_PMU.h"
#include "llvm/Transforms/PAETT/LLVM_PAETT.h"
#include "LLVM_PAETT_util.h"
#include "common.h"
#include <unordered_map>
#include <vector>
#include <algorithm>

using namespace llvm;
namespace {
    // template<class InstrumentMetrics>
    struct InstrmentByPerfPass : public ModulePass {
        static char ID;
        // InstrumentMetrics metrics;
        uint64_t mid;
        InstrmentByPerfPass() : ModulePass(ID) { 
            initializeInstrmentByPerfPassPass(*PassRegistry::getPassRegistry());
            //initializeInstrmentByPerfPassPass<InstrumentMetrics>(*PassRegistry::getPassRegistry());
            char* filterFile = getenv("PAETT_FILTER");
            if(filterFile) {
                FILE* fp = fopen(filterFile, "r");
                if(fp==NULL) {
                    printf("Warning: filter file %s could not open! Disable filtering\n", filterFile);
                    filterEnabled = false;
                } else {
                    filterEnabled = true;
                    uint64_t keyVal;
                    int is_parallel;
                    char buff[101];
                    while(EOF!=fscanf(fp, "%ld ", &keyVal)) {
                        fscanf(fp, "%d ", &is_parallel);
                        fscanf(fp, "%100[^\n]", buff);
                        std::string key(buff);
                        fscanf(fp, "%c", &buff[0]);
                        while(buff[0]!='\n') {
                            fscanf(fp, "%99[^\n]", &buff[1]);
                            key += std::string(buff);
                            fscanf(fp, "%c", &buff[0]);
                        }
                        filter.push_back(key);
                    }
                    fclose(fp);
                }
            } else {
                filterEnabled = false;
            }
            char* freqModFilterFile = getenv("PAETT_CCT_FREQUENCY_COMMAND_FILTER");
            if(freqModFilterFile) {
                if(filterFile) {
                    printf("Error: Both PAETT_FILTER and PAETT_CCT_FREQUENCY_COMMAND_FILTER are configured. Please configure only one of them at a time.\n");
                    printf("\tPAETT_FILTER = %s\n", filterFile);
                    printf("\tPAETT_CCT_FREQUENCY_COMMAND_FILTER = %s\n", freqModFilterFile);
                    exit(-1);
                }
                FILE* fp = fopen(freqModFilterFile, "r");
                if(fp==NULL) {
                    printf("Warning: filter file for frequency optimization %s could not open!\n", freqModFilterFile);
                    CCTFreqModEnabled = false;
                    // exit(-1);
                } else {
                    CCTFreqModEnabled = true;
                    uint64_t keyVal;
                    int is_parallel;
                    char buff[101];
                    // CCT Filter File Format: <keyVal> <is_parallel> <debug_info>\n
                    while(EOF!=fscanf(fp, "%ld ", &keyVal)) {
                        fscanf(fp, "%d ", &is_parallel);
                        fscanf(fp, "%100[^\n]", buff);
                        std::string key(buff);
                        fscanf(fp, "%c", &buff[0]);
                        while(buff[0]!='\n') {
                            fscanf(fp, "%99[^\n]", &buff[1]);
                            key += std::string(buff);
                            fscanf(fp, "%c", &buff[0]);
                        }
                        filterMap[key] = keyVal;
                        isParallelMap[key] = is_parallel;
                        //printf("%s %d %ld\n",(key+"\0").c_str(), key.c_str()[key.size()-1], keyVal);
                        // printf("%s %d %ld\n", (key+"\0").c_str(), is_parallel, keyVal);
                    }
                    fclose(fp);
                }
            } else {
                CCTFreqModEnabled = false;
            }
        }
        ~InstrmentByPerfPass() {};
        void getAnalysisUsage(AnalysisUsage &AU) const override {
            AU.setPreservesCFG();
            AU.addRequired<LoopInfoWrapperPass>();
        }
        virtual bool runOnModule(Module &M) {
            PAETT_label_num = 0;
            LLVMContext &C = M.getContext();
            // common used types
		    Type* VoidTy = Type::getVoidTy(C); 
            // prepare for instrumentation
            std::string m_name = M.getName().str();
            // func prototypes
            Type* keyType;
            if(CCTFreqModEnabled) {
                keyType = Type::getInt64Ty(C);
            } else {
                // Although the PAETT_inst uses unsigned 64-bit integer as input argument of the API, 
                // Int8Ptr type is more nature for LLVM strong type conversion (pointer to a char array)
                keyType = Type::getInt8PtrTy(C);
            }
#ifdef USE_OLD_LLVM
            hookInit =Function::Create(FunctionType::get(VoidTy, {}, false), Function::ExternalLinkage, "PAETT_inst_init", &M);
            hookEnter = Function::Create(FunctionType::get(VoidTy, {keyType}, false), Function::ExternalLinkage, "PAETT_inst_enter", &M);
            hookExit = Function::Create(FunctionType::get(VoidTy, {keyType}, false), Function::ExternalLinkage, "PAETT_inst_exit", &M);
            hookThreadInit = Function::Create(FunctionType::get(VoidTy, {keyType}, false), Function::ExternalLinkage, "PAETT_inst_thread_init", &M);
            hookThreadFini = Function::Create(FunctionType::get(VoidTy, {keyType}, false), Function::ExternalLinkage, "PAETT_inst_thread_fini", &M);
            hookFinalize = Function::Create(FunctionType::get(VoidTy, {}, false), Function::ExternalLinkage, "PAETT_inst_finalize", &M);
            hookDebugPrint = Function::Create(FunctionType::get(VoidTy, {}, false), Function::ExternalLinkage, "PAETT_print", &M);
#else
            hookInit = M.getOrInsertFunction("PAETT_inst_init", VoidTy);
            hookEnter = M.getOrInsertFunction("PAETT_inst_enter", VoidTy, keyType);
            hookExit = M.getOrInsertFunction("PAETT_inst_exit", VoidTy, keyType);
            hookThreadInit = M.getOrInsertFunction("PAETT_inst_thread_init", VoidTy, keyType);
            hookThreadFini = M.getOrInsertFunction("PAETT_inst_thread_fini", VoidTy, keyType);
            hookFinalize = M.getOrInsertFunction("PAETT_inst_finalize", VoidTy);
            hookDebugPrint = M.getOrInsertFunction("PAETT_print", VoidTy);
#endif
            // begin instrumentation
            for(Module::iterator F = M.begin(), E = M.end(); F!= E; ++F) {
                if (F->isDeclaration())
                    continue;
                // insert update calls first to make sure it will not conflict with inserted final calls.
                insertInstrumentationCalls(M, &(*F));
                if(F->getName()=="main" || F->getName()=="MAIN_") {
                    // insert init function into entry bbl of main function
                    Instruction *newInst = CallInst::Create(hookInit, "");
                    newInst->insertBefore(&(*F->getEntryBlock().getFirstNonPHIOrDbgOrLifetime()));
                    newInst = CallInst::Create(hookDebugPrint, "");
                    newInst->insertBefore(&(*F->getEntryBlock().getFirstNonPHIOrDbgOrLifetime()));
                }
	            for(Function::iterator BB = F->begin(), E = F->end(); BB != E; ++BB) {
				    InstrmentByPerfPass::runOnBasicBlock(BB);
			    }
            }
            return true;
        }
        // instrument here
        virtual bool runOnBasicBlock(Function::iterator &BB) {
            Function* bb_func = BB->getParent();
            StringRef f_name = bb_func->getName();	
            std::string func_name = f_name.str();	
            std::string bb_name = BB->getName().str();
            for(BasicBlock::iterator BI = BB->begin(), BE = BB->end(); BI != BE; ++BI) {
                // Insert profile output function before program exits
                if(dyn_cast<ReturnInst>(&(*BI))) {
                    // This is quite C-like hack. TODO: general solution
                    if (func_name=="main" || func_name=="MAIN_") {
                        Instruction *newInst = CallInst::Create(hookFinalize,"");
                        newInst->insertBefore(&(*BI));
                    }
                }
                if(auto *op=dyn_cast<CallInst>(&(*BI))) {
                    Function* f = op->getCalledFunction();
				    if (!f) continue;
                    StringRef callee = op->getCalledFunction() -> getName();
                    std::string calleeName = callee.str();
                    if(calleeName=="exit") {
                        // C program may exit by calling exit, not returning
                        Instruction *newInst = CallInst::Create(hookFinalize,"");
                        newInst->insertBefore(&(*BI));
                    }
                }
            }
            return true;
        }
        private:
#ifdef USE_OLD_LLVM
        typedef Function* FunctionCallee;
#endif
        FunctionCallee hookInit; // instrumentation function called before entering main
        FunctionCallee hookEnter; // instrumentation function called before Loop/Function begin
        FunctionCallee hookExit; // instrumentation function called after Loop/Function finish
        FunctionCallee hookFinalize; // instrumentation function called before program exit
        FunctionCallee hookThreadInit;
        FunctionCallee hookThreadFini;
        FunctionCallee hookDebugPrint;
        PAETT_Utils utils;
        uint64_t PAETT_label_num;
        std::unordered_map<std::string, std::string> keyLabelMap;
        std::vector<std::string> filter;
        bool filterEnabled;
        std::unordered_map<std::string, uint64_t> filterMap;
        std::unordered_map<std::string, int> isParallelMap;
        bool CCTFreqModEnabled;
        Value* getInstKey(Module &M, LLVMContext &C, std::string debug_info, bool force=false) {
            if(utils.isInvalidString(debug_info)) return NULL;
            // white list filtering if enabled
            if(!force && filterEnabled && std::find(filter.begin(), filter.end(), debug_info)==filter.end()) return NULL;
            // if CCT Frequency optimization filter is configured, use the specified key value instead
            if(CCTFreqModEnabled) {
                auto keyPair = filterMap.find(debug_info);
                if(keyPair!=filterMap.end())
                    return llvm::ConstantInt::get(Type::getInt64Ty(C), keyPair->second);
                else if (!force)
                    return NULL;
                else // force to generate a key
                    return llvm::ConstantInt::get(Type::getInt64Ty(C), 0);
            }
            // otherwise, generate a global string containing the debug_info and take the address of the beginning of the string as key value
            // this will guarantee the different string has different key value and same code location will has the same key value
            // and also it will provide the actual debug information for profiling tool to give better/more readable profiling results.
            ArrayType* StringTy = ArrayType::get(llvm::Type::getInt8Ty(C), debug_info.size()+1);
            Type* Int8Ty = Type::getInt8Ty(C);
            std::vector<llvm::Constant*> values;
            for(size_t k=0;k<debug_info.size();++k) {
                llvm::Constant* cv = llvm::ConstantInt::get(Int8Ty, debug_info[k]);
                values.push_back(cv);
            }
            values.push_back(llvm::ConstantInt::get(Int8Ty, 0));
            std::string label;
            auto iter = keyLabelMap.find(debug_info);
            if(iter==keyLabelMap.end()) {
                // generate unique label for paett key
                label  = std::string(".paett.key.");
                label += std::to_string(PAETT_label_num);
                label += std::string(".")+M.getName().str();
                keyLabelMap[debug_info] = label;
                ++PAETT_label_num;
            } else {
                label = iter->second;
            }
            // printf("KEY LABEL: %s : %s\n",label.c_str(), debug_info.c_str());
            // now generate and initialze global constant string of debug info
            auto globalDeclaration = (llvm::GlobalVariable*) M.getOrInsertGlobal(label.c_str(), StringTy);
            globalDeclaration->setInitializer(llvm::ConstantArray::get(StringTy, values));
            globalDeclaration->setConstant(true);
            globalDeclaration->setLinkage(llvm::GlobalValue::LinkageTypes::ExternalLinkage);
            globalDeclaration->setUnnamedAddr (llvm::GlobalValue::UnnamedAddr::Global);
            // 4. Return a cast to an i8*
            return llvm::ConstantExpr::getBitCast(globalDeclaration, Int8Ty->getPointerTo());
        }
        void getFunctionExitOps(Function* F, std::vector<Instruction*>& list) {
            for(Function::iterator BB = F->begin(), E = F->end(); BB != E; ++BB) {
			 	for(BasicBlock::iterator BI = BB->begin(), BE = BB->end(); BI != BE; ++BI) {
                    if(auto *op=dyn_cast<CallInst>(&(*BI))) {
                        Function* calledFunc = op->getCalledFunction();
                        if(calledFunc) {
                            std::string name = calledFunc->getName().str();
                            if(name=="exit") {
                                list.push_back(op);
                            }
                        }
                    }
                    if(auto *op=dyn_cast<ReturnInst>(&(*BI))) {
                        list.push_back(op);
                    }
                }
            }
        }
        void insertInstrumentationCalls(Module &M, Function* F) {
            std::string Fname = F->getName().str();
            LLVMContext &C = F->getContext();
            Value* key;
            if(Fname.find(".omp")!=std::string::npos) {
                // printf("****** Hanlding OMP function: %s (%s)\n",Fname.c_str(),utils.func2string(F).c_str());
                // key = getInstKey(M, C, utils.func2string(F), true);
                // printf("Value* key=%p\n",key);
                // assert(key!=NULL);
                // printf("Inserting Enter...\n");
                // Instruction *enterInst = CallInst::Create(hookEnter,{key});
                // enterInst->insertBefore(&(*F->getEntryBlock().getFirstNonPHIOrDbgOrLifetime()));
                // std::vector<Instruction*> list;
                // printf("Inserting Exit...\n");
                // getFunctionExitOps(F, list);
                // for(int i=0, n=list.size();i<n;++i) {
                //     printf("%d...\n", i);
                //     Instruction *ExitInst = CallInst::Create(hookExit,{key});
                //     ExitInst->insertBefore(list[i]);
                // }
                // printf("****** Finish Handling OMP function: %s (%s)\n", Fname.c_str(),utils.func2string(F).c_str());
                return ;
            }
            // LoopInfo must be obtained by LoopInfoWrapperPass
            LoopInfo &LI = getAnalysis<LoopInfoWrapperPass>(*F).getLoopInfo();
            auto ll = LI.getLoopsInPreorder();
            std::vector<Loop*> list;
#define MERGE_NESTED_LOOPS_IF_POSSIBLE
#ifdef MERGE_NESTED_LOOPS_IF_POSSIBLE
            // Remove invalid/nested inner loops
            // list is in preorder
            for(auto lkey : ll) {
                if(lkey->isInvalid() || lkey->getParentLoop()) {
                    continue; // the loop is invalid or nested in an outer loop, so skip it.
                }
                list.push_back(lkey);
            }
#endif
            IRBuilder<> builder(C);
            for(auto lkey : list) {
                // First get context key of this loop
                if(lkey->isInvalid()) continue; // the loop is no longer invalid, so skip it.
                std::string lkeyStr = utils.loop2string(lkey);
                key = getInstKey(M, C, lkeyStr); // get key value associated to this loop's debug info
                if(key==NULL) continue; // invalid key
                int is_parallel = isParallelMap[lkeyStr];
                if(is_parallel) {
                    Instruction *threadInitInst = CallInst::Create(hookThreadInit,{key});
                    threadInitInst->insertBefore(utils.getLoopInsertPrePoint(lkey));
                } else {
                    Instruction *enterInst = CallInst::Create(hookEnter,{key});
                    enterInst->insertBefore(utils.getLoopInsertPrePoint(lkey));
                }
                // create paett_inst_exit function call and insert it after exiting this loop
                std::vector<Instruction*> insPos;
                utils.getLoopInsertPostPoint(lkey, insPos);
                for(int i=0, n=insPos.size();i<n;++i) {
                    if(is_parallel) {
                        Instruction *exitInst = CallInst::Create(hookThreadFini,{key});
                        exitInst->insertBefore(insPos[i]);
                    } else {
                        Instruction *ExitInst = CallInst::Create(hookExit,{key});
                        ExitInst->insertBefore(insPos[i]);
                    }
                }
            } // end iterate loops
            // Insert enter/exit pair for every function call to maintain calling context
            for(Function::iterator BB = F->begin(), E = F->end(); BB != E; ++BB) {
			 	for(BasicBlock::iterator BI = BB->begin(), BE = BB->end(); BI != BE; ++BI) {
                    if(auto *op=dyn_cast<CallInst>(&(*BI))) {
                        Function* f = op->getCalledFunction();
                        if(!f || f->isIntrinsic()) continue;
                        std::string name = op->getCalledFunction()->getName().str();
                        // ignore inserted PAETT library calls
                        if(name.find("PAETT_")!=std::string::npos) continue;
                        // ignore openmp function calls
                        if(name=="__kmpc_fork_call" || name=="__kmpc_fork_teams") {
                            key = getInstKey(M, C, utils.ins2string(op));
                            if(key==NULL) continue; // invalid key
                            /****************************************
                             * call PAETT_inst_thread_init(key)     *
                             * // call PAETT_inst_enter(key)        *
                             * call __kmpc_fork_*...                *
                             * call PAETT_inst_thread_fini(key)     *
                             ****************************************/
                            Instruction *threadInitInst = CallInst::Create(hookThreadInit,{key});
                            threadInitInst->insertBefore(op);
                            Instruction *exitInst = CallInst::Create(hookThreadFini,{key});
                            exitInst->insertAfter(op);
                        } else {
                            if(name.find("omp")!=std::string::npos || name.find("__kmpc")!=std::string::npos) continue;
                            std::string keyStr = utils.ins2string(op);
                            key = getInstKey(M, C, keyStr);
                            if(key==NULL) continue; // invalid key
                            if(isParallelMap[keyStr]) {
                                Instruction *threadInitInst = CallInst::Create(hookThreadInit,{key});
                                threadInitInst->insertBefore(op);
                                Instruction *exitInst = CallInst::Create(hookThreadFini,{key});
                                exitInst->insertAfter(op);
                            } else {
                                Instruction *enterInst = CallInst::Create(hookEnter,{key});
                                enterInst->insertBefore(op);
                                Instruction *exitInst = CallInst::Create(hookExit,{key});
                                exitInst->insertAfter(op);
                            }
                        }
                    }
#ifndef USE_OLD_LLVM
                    if(auto *op=dyn_cast<CallBrInst>(&(*BI))) {
                        std::string keyStr = utils.ins2string(op);
                        key = getInstKey(M, C, keyStr);
                        if(key==NULL) continue; // invalid key
                        int is_parallel = isParallelMap[keyStr];
                        if(is_parallel) {
                            Instruction *threadInitInst = CallInst::Create(hookThreadInit,{key});
                            threadInitInst->insertBefore(op);
                        } else {
                            Instruction *enterInst = CallInst::Create(hookEnter,{key});
                            enterInst->insertBefore(op);
                        }
                        auto dest = op->getDefaultDest();
                        Instruction *exitInst = CallInst::Create(hookExit,{key});
                        exitInst->insertBefore(&(*(dest->getFirstNonPHIOrDbgOrLifetime())));
                        auto indirectDests = op->getIndirectDests();
                        for(auto suc : indirectDests) {
                            if(is_parallel) {
                                Instruction *exitInst2 = CallInst::Create(hookThreadFini,{key});
                                exitInst2->insertBefore(&(*(suc->getFirstNonPHIOrDbgOrLifetime())));
                            } else {
                                Instruction *exitInst2 = CallInst::Create(hookExit,{key});
                                exitInst2->insertBefore(&(*(suc->getFirstNonPHIOrDbgOrLifetime())));
                            }
                        }
                    }
#endif
                    if(auto *op=dyn_cast<InvokeInst>(&(*BI))) {
                        std::string keyStr = utils.ins2string(op);
                        key = getInstKey(M, C, keyStr);
                        if(key==NULL) continue; // invalid key
                        if(isParallelMap[keyStr]) {
                            Instruction *threadInitInst = CallInst::Create(hookThreadInit,{key});
                            threadInitInst->insertBefore(op);
                            auto unwind = op->getUnwindDest();
                            Instruction *exitInstU = CallInst::Create(hookThreadFini,{key});
                            exitInstU->insertBefore(&(*(unwind->getFirstInsertionPt()))); 
                            auto normal = op->getNormalDest();
                            Instruction *exitInstN = CallInst::Create(hookThreadFini,{key});
                            exitInstN->insertBefore(&(*(normal->getFirstInsertionPt())));
                        } else {
                            Instruction *enterInst = CallInst::Create(hookEnter,{key});
                            enterInst->insertBefore(op);
                            auto unwind = op->getUnwindDest();
                            Instruction *exitInstU = CallInst::Create(hookExit,{key});
                            exitInstU->insertBefore(&(*(unwind->getFirstInsertionPt()))); 
                            auto normal = op->getNormalDest();
                            Instruction *exitInstN = CallInst::Create(hookExit,{key});
                            exitInstN->insertBefore(&(*(normal->getFirstInsertionPt())));
                        }
                    }
                }
            }
        }
    };
}

char InstrmentByPerfPass::ID = 0;

Pass* llvm::createInstByPerfPass() {
  return new InstrmentByPerfPass();
}

#define INITIALIZE_TEMPLATE_PASS_BEGIN(passName, arg, name, cfg, analysis)              \
  static void *initialize##passName##PassOnce(PassRegistry &Registry) {

#define INITIALIZE_TEMPLATE_PASS_END(passName, arg, name, cfg, analysis)                \
  PassInfo *PI = new PassInfo(                                                 \
      name, arg, &passName::ID,                                                \
      PassInfo::NormalCtor_t(callDefaultCtor<passName>), cfg, analysis);       \
  Registry.registerPass(*PI, true);                                            \
  return PI;                                                                   \
  }                                                                            \
  static llvm::once_flag Initialize##passName##PassFlag;                       \
  void llvm::initialize##passName##Pass(PassRegistry &Registry) {              \
    llvm::call_once(Initialize##passName##PassFlag,                            \
                    initialize##passName##PassOnce, std::ref(Registry));       \
  }

// #define INITIALIZE_PASS_FROM_TEMP(passName, basePassName, T) \
//   void llvm::initialize##passName##Pass(PassRegistry &Registry) { llvm::initialize##basePassName##Pass<T>(Registry); }

INITIALIZE_TEMPLATE_PASS_BEGIN(InstrmentByPerfPass, "InstrmentByPerfPass", 
                      "will compile with PAETT instrumentation", 
                      false, false)
INITIALIZE_PASS_DEPENDENCY(LoopInfoWrapperPass) // Or whatever your Pass dependencies
INITIALIZE_TEMPLATE_PASS_END(InstrmentByPerfPass, "InstrmentByPerfPass",
                    "will compile with PAETT instrumentation", 
                    false, false)