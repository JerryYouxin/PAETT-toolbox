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
#include "llvm/Transforms/PAETT/LLVM_PAETT.h"
#include "LLVM_PAETT_model.h"
#include "LLVM_PAETT_util.h"
#include "common.h"
// data types
#include <unordered_map>
#include <vector>
// for file control
#include <sys/file.h>
#include <unistd.h>

#define ENABLE_POST_FREQMOD

using namespace llvm;
namespace {
    class FreqModPass : public ModulePass {
        public:
        static char ID;
        uint64_t mid;
#ifdef USE_OLD_LLVM
        typedef Function* FunctionCallee;
#endif
        FunctionCallee hookInit; // instrumentation function called before entering main
        FunctionCallee hookFinalize; // instrumentation function called before program exit
        FunctionCallee hookCUFreqMod;
        FunctionCallee hookCFreqMod;
        FunctionCallee hookUFreqMod;
        FunctionCallee hookCUFreqModAll;
        FunctionCallee hookCFreqModAll;
        FunctionCallee hookUFreqModAll;
        FunctionCallee hookCUFreqModPost;
        FunctionCallee hookCFreqModPost;
        FunctionCallee hookUFreqModPost;
        FunctionCallee hookAffinityAll;
        FunctionCallee hookAffinityRecover;
        FunctionCallee hookThread;
        ModelAdapter adapter;
        FreqModPass() : ModulePass(ID) {
            initializeFreqModPassPass(*PassRegistry::getPassRegistry());
            // get frequency modification commands from model adapter.
            // TODO: the command list can be optimized by merging same commands of nested loop together.
            adapter.init();
        }
        ~FreqModPass() {};
        void getAnalysisUsage(AnalysisUsage &AU) const override {
            AU.setPreservesCFG();
            AU.addRequired<LoopInfoWrapperPass>();
        }
        
        virtual bool runOnModule(Module &M) {
            LLVMContext &C = M.getContext();
            // common used types
		    Type* VoidTy = Type::getVoidTy(C); 
            PAETT_Utils utils;
            // obtain neccessary analysis data
            std::string m_name = M.getName().str();
            utils.readKeyMap(m_name);
            // function hooks
#ifdef USE_OLD_LLVM
            hookInit = Function::Create(FunctionType::get(VoidTy, {}, false), Function::ExternalLinkage, "PAETT_init", &M);
            hookFinalize = Function::Create(FunctionType::get(VoidTy, {}, false), Function::ExternalLinkage, "PAETT_finalize", &M);
            hookCUFreqModAll = Function::Create(FunctionType::get(VoidTy, {Type::getInt64Ty(C), Type::getInt64Ty(C)}, false), Function::ExternalLinkage, "PAETT_modFreqAll", &M);
            hookThread =Function::Create(FunctionType::get(VoidTy, {Type::getInt64Ty(C)}, false), Function::ExternalLinkage, "PAETT_modOMPThread", &M);
#else
            hookInit = M.getOrInsertFunction("PAETT_init", VoidTy);
            hookFinalize = M.getOrInsertFunction("PAETT_finalize", VoidTy);
            hookCUFreqModAll= M.getOrInsertFunction("PAETT_modFreqAll", VoidTy, Type::getInt64Ty(C), Type::getInt64Ty(C));
            hookThread = M.getOrInsertFunction("PAETT_modOMPThread", VoidTy, Type::getInt64Ty(C));
#endif
            for(Module::iterator F=M.begin(), E=M.end(); F!=E;++F) {
                if (F->isDeclaration())
                    continue;
                // handle loop first
                LoopInfo& LI = getAnalysis<LoopInfoWrapperPass>(*F).getLoopInfo();
                auto ll = LI.getLoopsInPreorder();
                for(auto lkey : ll) {
                    if(lkey->isInvalid()) continue;
                    printf("Matching for [%s]...",utils.loop2string(lkey).c_str());
                    uint64_t key = utils.lookupKey(utils.loop2string(lkey)); // get key value associated to this loop's debug info
                    if(key==CCT_INVALID_KEY) {
                        printf("Not found. Next\n");
                        continue;
                    }
                    printf("Matched. getFreqCommand...");
                    FreqCommand_t command = adapter.getFreqCommand(key);
                    if(isInvalidFreqCommand(command)) {
                        printf("Invalid FreqCommand returned. Skip\n");
                        continue; // quick pass when the command is invalid
                    }
                    printf("getFreqCommand:[%ld, pre=(%ld, %ld, %ld), post=(%ld, %ld, %ld)]\n",command.key,
                        command.pre.core,command.pre.uncore,command.pre.thread,
                        command.post.core,command.post.uncore,command.post.thread);
                    insertFreqModInstruction(C, utils.getLoopInsertPrePoint(lkey), command.pre);
                    // create post freqmod function call and insert it after exiting this loop
                    std::vector<Instruction*> insPos;
                    utils.getLoopInsertPostPoint(lkey, insPos);
                    for(int i=0, n=insPos.size();i<n;++i) {
#ifdef ENABLE_POST_FREQMOD
                        insertFreqModInstruction(C, insPos[i], command.post);
#else
                        //insertFreqModInstruction(C, insPos[i], 2400000, 2585);
                        insertFreqModInstruction(C, insPos[i], { 1200000, 2570, 28 });
#endif
                    }
                }
                // Insert enter/exit pair for every function call to maintain calling context
                for(Function::iterator BB = F->begin(), E = F->end(); BB != E; ++BB) {
                    for(BasicBlock::iterator BI = BB->begin(), BE = BB->end(); BI != BE; ++BI) {
                        if(auto *op=dyn_cast<CallInst>(&(*BI))) {
                            Function* f = op->getCalledFunction();
                            if(!(!f || f->isIntrinsic())) {
                                std::string name = op->getCalledFunction()->getName().str();
                                if(name=="__kmpc_fork_call" || name=="__kmpc_fork_teams") {
                                    printf("Matching [%s]: %s:",utils.ins2string(&(*BI)).c_str(), name.c_str());
                                    //insertAffinity(C, op);
                                }
                            }
                        }
                        uint64_t key = utils.lookupKey(utils.ins2string(&(*BI)));
                        if(auto *op=dyn_cast<CallInst>(&(*BI))) {
                            Function* f = op->getCalledFunction();
                            if(!(!f || f->isIntrinsic())) {
                                std::string name = op->getCalledFunction()->getName().str();
                                if(name=="__kmpc_fork_call" || name=="__kmpc_fork_teams") {
                                    printf("key=%lx:\n",key);
                                }
                            }
                        }
                        if(key==CCT_INVALID_KEY) continue;
                        FreqCommand_t command = adapter.getFreqCommand(key);
                        if(isInvalidFreqCommand(command)) continue; // quick pass when the command is invalid
                        printf("Matched [%s]: ",utils.ins2string(&(*BI)).c_str());
                        printf("getFreqCommand:[%ld, pre=(%ld, %ld, %ld), post=(%ld, %ld, %ld)]\n",command.key,
                            command.pre.core,command.pre.uncore,command.pre.thread,
                            command.post.core,command.post.uncore,command.post.uncore);
                        if(auto *op=dyn_cast<CallInst>(&(*BI))) {
                            Function* f = op->getCalledFunction();
                            if(!f || f->isIntrinsic()) {
                                printf("Warning: Function (%lx:%s) matched command %d %d %d is declaration or intrinsic! Ignore this match.\n",command.key, utils.ins2string(&(*BI)).c_str(), command.pre.core, command.pre.uncore, command.pre.thread);
                                continue;
                            }
                            assert(!(!f || f->isIntrinsic()));
                            std::string name = op->getCalledFunction()->getName().str();
                            if(name=="__kmpc_fork_call" || name=="__kmpc_fork_teams") {
                                printf("Inserting for parallel region: %s\n",name.c_str());
                                insertFreqModInstruction(C, op, command.pre);
                            } else {
                                insertFreqModInstruction(C, op, command.pre);
                            }
#ifdef ENABLE_POST_FREQMOD
                            insertFreqModInstructionAfter(C, op, command.post);
#else
                            insertFreqModInstructionAfter(C, op, { 1200000, 2570, 28 });
#endif
                        }
#ifndef USE_OLD_LLVM
                        if(auto *op=dyn_cast<CallBrInst>(&(*BI))) {
                            insertFreqModInstruction(C, op, command.pre);
#ifdef ENABLE_POST_FREQMOD
                            for(unsigned int i=0, n=op->getNumSuccessors();i<n;++i) {
                                auto suc = op->getSuccessor(i);
                                insertFreqModInstruction(C, &(*(suc->getFirstNonPHIOrDbgOrLifetime())), command.pre);
                            }
#endif
                        }
#endif
                        if(auto *op=dyn_cast<InvokeInst>(&(*BI))) {
                            insertFreqModInstruction(C, op, command.pre);
#ifdef ENABLE_POST_FREQMOD
                            auto unwind = op->getUnwindDest();
#ifdef USE_OLD_LLVM
                            insertFreqModInstruction(C, &(*(unwind->getFirstInsertionPt())), command.post);
#else
                            Instruction* unw = &(*(unwind->getTerminator()));
                            for(unsigned int i=0, n=unw->getNumSuccessors();i<n;++i) {
                                auto suc = unw->getSuccessor(i);
                                insertFreqModInstruction(C, &(*(suc->getFirstInsertionPt())), command.post);
                            }
#endif
                            auto normal = op->getNormalDest();
                            insertFreqModInstruction(C, &(*(normal->getFirstInsertionPt())), command.post);
#endif
                        }
                    }
                }
            }
            //errs() << "**** NEXT\n" ;
            // insert neccessary init/finalize functions at entry/exit of program
            for(Module::iterator F = M.begin(), E = M.end(); F!= E; ++F) {
                if (F->isDeclaration())
                    continue;
                printf("F name = %s\n", F->getName().str().c_str());
                if(F->getName()=="main" || F->getName()=="MAIN_") {
                    // insert init function into entry bbl of main function
                    Instruction *newInst = CallInst::Create(hookInit);
                    newInst->insertBefore(&(*F->getEntryBlock().getFirstNonPHIOrDbgOrLifetime()));
                    FreqCommand_t command = adapter.getFreqCommand(CCT_ROOT_KEY);
                    if(!isInvalidFreqCommand(command)) {
                        // the root key command is valid, insert frequency command defined in pre
                        // Note that ROOT key's post freq is meaningless, so ignore it
                        insertFreqModInstructionAfter(C, newInst, command.pre);
                    }
                }
	            for(Function::iterator BB = F->begin(), E = F->end(); BB != E; ++BB) {
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
                }
            }
            return true;
        }

        private:
        void insertFreqModInstruction(LLVMContext &C, Instruction* insPos, freqPair command) {
            uint64_t core = command.core;
            uint64_t uncore = command.uncore; // MAKE_UNCORE_VALUE_BY_FREQ(uncoreFreq);
            if(core || uncore) {
                // modify core and uncore frequency
                errs() << "Insert CORE UNCORE frequency mod " << core << " " << uncore << "\n";
                Instruction *freqmodInst = CallInst::Create(hookCUFreqModAll, { ConstantInt::get(Type::getInt64Ty(C), core), ConstantInt::get(Type::getInt64Ty(C), uncore) } );
                freqmodInst->insertBefore(insPos);
            } else {
                // DO NOTHING
            }
            if(command.thread!=0) {
                Instruction *ThreadInst = CallInst::Create(hookThread, {ConstantInt::get(Type::getInt64Ty(C), command.thread)} );
                ThreadInst->insertBefore(insPos);
            }
        }
        Instruction* insertFreqModInstructionAfter(LLVMContext &C, Instruction* insPos, freqPair command) {
            uint64_t core = command.core;
            uint64_t uncore = command.uncore; // MAKE_UNCORE_VALUE_BY_FREQ(uncoreFreq);
            if(command.thread!=0) {
                Instruction *ThreadInst = CallInst::Create(hookThread, {ConstantInt::get(Type::getInt64Ty(C), command.thread)} );
                ThreadInst->insertAfter(insPos);
            }
            if(core || uncore) {
                // modify core and uncore frequency
                errs() << "Insert CORE UNCORE frequency mod " << core << " " << uncore << "\n";
                Instruction *freqmodInst = CallInst::Create(hookCUFreqModAll, { ConstantInt::get(Type::getInt64Ty(C), core), ConstantInt::get(Type::getInt64Ty(C), uncore) } );
                freqmodInst->insertAfter(insPos);
                return freqmodInst;
            } else {
                // DO NOTHING
            }
            return insPos;
        }
    };
}

char FreqModPass::ID = 0;

Pass* llvm::createFreqModPass() {
  return new FreqModPass();
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

INITIALIZE_TEMPLATE_PASS_BEGIN(FreqModPass, "FreqModPass", 
                      "will compile with cpu power saving methodology (profile needed)", 
                      false, false)
INITIALIZE_PASS_DEPENDENCY(LoopInfoWrapperPass) // Or whatever your Pass dependencies
INITIALIZE_TEMPLATE_PASS_END(FreqModPass, "FreqModPass",
                    "will compile with cpu power saving methodology (profile needed)", 
                    false, false)
