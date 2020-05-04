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

using namespace llvm;
namespace {
    // template<class InstrumentMetrics>
    struct InstrmentByPerfPass : public ModulePass {
        static char ID;
        // InstrumentMetrics metrics;
        uint64_t mid;
        // const std::string ignoreList[] = 
        //     {"PAETT_inst_init","PAETT_inst_finalize","PAETT_inst_enter","PAETT_inst_exit","PAETT_print"}; // TODO malloc freee
        InstrmentByPerfPass() : ModulePass(ID) { 
            initializeInstrmentByPerfPassPass(*PassRegistry::getPassRegistry());
            //initializeInstrmentByPerfPassPass<InstrumentMetrics>(*PassRegistry::getPassRegistry());
            // metrics.Register(); 
            // metrics.printEventList();
        }
        ~InstrmentByPerfPass() {};
        void getAnalysisUsage(AnalysisUsage &AU) const override {
            AU.setPreservesCFG();
            AU.addRequired<LoopInfoWrapperPass>();
        }
        virtual bool runOnModule(Module &M) {
            LLVMContext &C = M.getContext();
            // common used types
		    Type* VoidTy = Type::getVoidTy(C); 
            // prepare for instrumentation
            std::string m_name = M.getName().str();
            // read keymap if exists
            //utils.readKeyMap(m_name, false/*disable safe_check*/);
            //mid = utils.getMID(m_name);
            // global variables (arrays of event)
            // gEvents = new GlobalVariable(M, metrics.getPerfEventListType(C), false, GlobalValue::LinkageTypes::InternalLinkage, metrics.getPerfEventList(C), "log.events");
            // func prototypes
#ifdef USE_OLD_LLVM
            //hookInit =Function::Create(FunctionType::get(VoidTy, {Type::getInt32Ty(C), gEvents->getType()}, false), Function::ExternalLinkage, "PAETT_inst_init", &M);
            hookInit =Function::Create(FunctionType::get(VoidTy, {}, false), Function::ExternalLinkage, "PAETT_inst_init", &M);
            hookEnter = Function::Create(FunctionType::get(VoidTy, {Type::getInt8PtrTy(C)}, false), Function::ExternalLinkage, "PAETT_inst_enter", &M);
            hookExit = Function::Create(FunctionType::get(VoidTy, {Type::getInt8PtrTy(C)}, false), Function::ExternalLinkage, "PAETT_inst_exit", &M);
            hookThreadInit = Function::Create(FunctionType::get(VoidTy, {Type::getInt8PtrTy(C)}, false), Function::ExternalLinkage, "PAETT_inst_thread_init", &M);
            hookThreadFini = Function::Create(FunctionType::get(VoidTy, {Type::getInt8PtrTy(C)}, false), Function::ExternalLinkage, "PAETT_inst_thread_fini", &M);
            // hookEnter = Function::Create(FunctionType::get(VoidTy, {Type::getInt64Ty(C)}, false), Function::ExternalLinkage, "PAETT_inst_enter", &M);
            // hookExit = Function::Create(FunctionType::get(VoidTy, {Type::getInt64Ty(C)}, false), Function::ExternalLinkage, "PAETT_inst_exit", &M);
            // hookThreadInit = Function::Create(FunctionType::get(VoidTy, {Type::getInt64Ty(C)}, false), Function::ExternalLinkage, "PAETT_inst_thread_init", &M);
            // hookThreadFini = Function::Create(FunctionType::get(VoidTy, {Type::getInt64Ty(C)}, false), Function::ExternalLinkage, "PAETT_inst_thread_fini", &M);
            hookFinalize = Function::Create(FunctionType::get(VoidTy, {}, false), Function::ExternalLinkage, "PAETT_inst_finalize", &M);
            hookDebugPrint = Function::Create(FunctionType::get(VoidTy, {}, false), Function::ExternalLinkage, "PAETT_print", &M);
#else
            // hookInit = M.getOrInsertFunction("PAETT_inst_init", VoidTy, Type::getInt32Ty(C), gEvents->getType());
            hookInit = M.getOrInsertFunction("PAETT_inst_init", VoidTy);
            hookEnter = M.getOrInsertFunction("PAETT_inst_enter", VoidTy, Type::getInt64Ty(C));
            hookExit = M.getOrInsertFunction("PAETT_inst_exit", VoidTy, Type::getInt64Ty(C));
            hookThreadInit = M.getOrInsertFunction("PAETT_inst_thread_init", VoidTy, Type::getInt64Ty(C));
            hookThreadFini = M.getOrInsertFunction("PAETT_inst_thread_fini", VoidTy, Type::getInt64Ty(C));
            hookFinalize = M.getOrInsertFunction("PAETT_inst_finalize", VoidTy);
            hookDebugPrint = M.getOrInsertFunction("PAETT_print", VoidTy);
#endif
            // begin instrumentation
            errs() << "=== Begin instrumentation ===\n";
            for(Module::iterator F = M.begin(), E = M.end(); F!= E; ++F) {
                if (F->isDeclaration())
                    continue;
		        errs().write_escaped(F->getName()) << "\n";
                // insert update calls first to make sure it will not conflict with inserted final calls.
                insertInstrumentationCalls(M, &(*F));
                if(F->getName()=="main" || F->getName()=="MAIN_") {
                    // insert init function into entry bbl of main function
                    errs().write_escaped(F->getName()) << "***************" << "\n";
                    // Instruction *newInst = CallInst::Create(hookInit, {metrics.getPerfEventListSize(C), gEvents});
                    Instruction *newInst = CallInst::Create(hookInit, "");
                    newInst->insertBefore(&(*F->getEntryBlock().getFirstNonPHIOrDbgOrLifetime()));
                    newInst = CallInst::Create(hookDebugPrint, "");
                    newInst->insertBefore(&(*F->getEntryBlock().getFirstNonPHIOrDbgOrLifetime()));
                }
	            for(Function::iterator BB = F->begin(), E = F->end(); BB != E; ++BB) {
				    InstrmentByPerfPass::runOnBasicBlock(BB);
			    }
            }
            // utils.printKeyMap(m_name);
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
                        // errs() << "!!!!!!!!! main\n";
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
                        // errs() << "!!!!!!!!! exit\n";
                        Instruction *newInst = CallInst::Create(hookFinalize,"");
                        newInst->insertBefore(&(*BI));
                    }
                }
            }
            return true;
        }
        private:
        // GlobalVariable* gEvents;// global variable perf events
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
        Value* getInstKey(Module &M, LLVMContext &C, std::string debug_info) {
            if(utils.isInvalidString(debug_info)) return NULL;
            ArrayType* StringTy = ArrayType::get(llvm::Type::getInt8Ty(C), debug_info.size()+1);
            Type* Int8Ty = Type::getInt8Ty(C);
            std::vector<llvm::Constant*> values;
            for(size_t k=0;k<debug_info.size();++k) {
                llvm::Constant* cv = llvm::ConstantInt::get(Int8Ty, debug_info[k]);
                values.push_back(cv);
            }
            values.push_back(llvm::ConstantInt::get(Int8Ty, 0));
            auto globalDeclaration = (llvm::GlobalVariable*) M.getOrInsertGlobal(debug_info.c_str(), StringTy);
            globalDeclaration->setInitializer(llvm::ConstantArray::get(StringTy, values));
            globalDeclaration->setConstant(true);
            globalDeclaration->setLinkage(llvm::GlobalValue::LinkageTypes::ExternalLinkage);
            globalDeclaration->setUnnamedAddr (llvm::GlobalValue::UnnamedAddr::Global);
            // 4. Return a cast to an i8*
            return llvm::ConstantExpr::getBitCast(globalDeclaration, Int8Ty->getPointerTo());
            // uint64_t key = utils.getInstKeyInt64(mid, debug_info);
            // return ConstantInt::get(Type::getInt64Ty(C), key);
        }
        void getFunctionExitOps(Function* F, std::vector<Instruction*>& list) {
            for(Function::iterator BB = F->begin(), E = F->end(); BB != E; ++BB) {
			 	for(BasicBlock::iterator BI = BB->begin(), BE = BB->end(); BI != BE; ++BI) {
                    if(auto *op=dyn_cast<CallInst>(&(*BI))) {
                        std::string name = op->getCalledFunction()->getName().str();
                        if(name=="exit") {
                            list.push_back(op);
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
            if(Fname.find(".omp")!=std::string::npos) {
                printf("****** SKIP Hanlding OMP function: %s\n",Fname.c_str());
                return ;
            }
            Value* key;
            // LoopInfo must be obtained by LoopInfoWrapperPass
            LoopInfo &LI = getAnalysis<LoopInfoWrapperPass>(*F).getLoopInfo();
            LLVMContext &C = F->getContext();
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
            //errs() << "==== 1 ======\n";
            IRBuilder<> builder(C);
            for(auto lkey : list) {
                // First get context key of this loop
                if(lkey->isInvalid()) continue; // the loop is no longer invalid, so skip it.
                key = getInstKey(M, C, utils.loop2string(lkey)); // get key value associated to this loop's debug info
                if(key==NULL) continue; // invalid key
                // key = builder.CreateGlobalString(utils.loop2string(lkey));
                Instruction *enterInst = CallInst::Create(hookEnter,{key});
                enterInst->insertBefore(utils.getLoopInsertPrePoint(lkey));
                // create paett_inst_exit function call and insert it after exiting this loop
                std::vector<Instruction*> insPos;
                utils.getLoopInsertPostPoint(lkey, insPos);
                for(int i=0, n=insPos.size();i<n;++i) {
                    Instruction *ExitInst = CallInst::Create(hookExit,{key});
                    ExitInst->insertBefore(insPos[i]);
                }
            } // end iterate loops
            // Insert enter/exit pair for every function call to maintain calling context
            // FILE* fp = fopen("parallel.region","a");
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
                            // printf("%ld(%d|%d):%s\n",utils.getInstKeyInt64(mid,utils.ins2string(op)),mid,utils.keySize,utils.ins2string(op).c_str());
                            // fprintf(fp,"%ld\n",utils.lookupKey(utils.ins2string(op)));
                            /****************************************
                             * call PAETT_inst_thread_init(key)     *
                             * call PAETT_inst_enter(key)           *
                             * call __kmpc_fork_*...                *
                             * call PAETT_inst_thread_fini(key)     *
                             ****************************************/
                            Instruction *enterInst = CallInst::Create(hookEnter,{key});
                            enterInst->insertBefore(op);
                            Instruction *threadInitInst = CallInst::Create(hookThreadInit,{key});
                            threadInitInst->insertBefore(op);
                            Instruction *exitInst = CallInst::Create(hookThreadFini,{key});
                            exitInst->insertAfter(op);
                        } else {
                            if(name.find("omp")!=std::string::npos || name.find("__kmpc")!=std::string::npos) continue;
                            key = getInstKey(M, C, utils.ins2string(op));
                            if(key==NULL) continue; // invalid key
                            Instruction *enterInst = CallInst::Create(hookEnter,{key});
                            enterInst->insertBefore(op);
                            Instruction *exitInst = CallInst::Create(hookExit,{key});
                            exitInst->insertAfter(op);
                        }
                    }
#ifndef USE_OLD_LLVM
                    if(auto *op=dyn_cast<CallBrInst>(&(*BI))) {
                        key = getInstKey(M, C, utils.ins2string(op));
                        if(key==NULL) continue; // invalid key
                        Instruction *enterInst = CallInst::Create(hookEnter,{key});
                        enterInst->insertBefore(op);
                        auto dest = op->getDefaultDest();
                        Instruction *exitInst = CallInst::Create(hookExit,{key});
                        exitInst->insertBefore(&(*(dest->getFirstNonPHIOrDbgOrLifetime())));
                        auto indirectDests = op->getIndirectDests();
                        for(auto suc : indirectDests) {
                            Instruction *exitInst2 = CallInst::Create(hookExit,{key});
                            exitInst2->insertBefore(&(*(suc->getFirstNonPHIOrDbgOrLifetime())));
                        }
                    }
#endif
                    if(auto *op=dyn_cast<InvokeInst>(&(*BI))) {
                        key = getInstKey(M, C, utils.ins2string(op));
                        if(key==NULL) continue; // invalid key
                        Instruction *enterInst = CallInst::Create(hookEnter,{key});
                        enterInst->insertBefore(op);
                        auto unwind = op->getUnwindDest();
#ifdef USE_OLD_LLVM
                        Instruction *exitInstU = CallInst::Create(hookExit,{key});
                        exitInstU->insertBefore(&(*(unwind->getFirstInsertionPt()))); 
#else
                        Instruction* unw = &(*(unwind->getTerminator()));
                        for(unsigned int i=0, n=unw->getNumSuccessors();i<n;++i) {
                            auto suc = unw->getSuccessor(i);
                            Instruction *exitInstU = CallInst::Create(hookExit,{key});
                            exitInstU->insertBefore(&(*(suc->getFirstInsertionPt())));   
                        }
#endif
                        auto normal = op->getNormalDest();
                        Instruction *exitInstN = CallInst::Create(hookExit,{key});
                        exitInstN->insertBefore(&(*(normal->getFirstInsertionPt())));
                    }
                }
            }
            // fclose(fp);
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