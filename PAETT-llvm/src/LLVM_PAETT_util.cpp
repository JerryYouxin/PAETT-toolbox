#include "LLVM_PAETT_util.h"
#include "common.h"
#include <stdint.h>
// for file control
#include <sys/file.h>
#include <unistd.h>

using namespace llvm;

void __lock() {
    int fd = open("keymap.lock",O_CREAT|O_EXCL);
    while(fd==-1) {
        usleep(50);
        fd = open("keymap.lock",O_CREAT|O_EXCL);
    }
    close(fd);
}

void __unlock() {
    remove("keymap.lock"); // release file lock
}

PAETT_Utils::PAETT_Utils() {
    // keySize = 0;
}

// // KeyMap write/read util functions. The file based locking method may lead to dead lock due to some reason
// void PAETT_Utils::printKeyMap(std::string m_name) {
//     printf("========== Print %s KeyMap ============\n",m_name.c_str());
//     uint64_t r;
//     const size_t ONE = 1;
//     __lock();
//     int fd = open(KEYMAP_FN,O_RDWR|O_CREAT,S_IRWXU);
//     if(fd==-1) {
//         errs() << "FETAL ERROR: Failed to open file " << KEYMAP_FN << ", err=" << fd << "\n";
//         __unlock();
//         exit(-1);
//     }
//     // flock will block when the lock is not available
//     if(int r=flock(fd, LOCK_EX)) {
//         errs() << "FETAL ERROR: Failed to lock file " << KEYMAP_FN << ", err=" << r << "\n";
//         __unlock();
//         exit(-1);
//     }
//     FILE* fp = fdopen(fd,"ab+");
//     for(std::unordered_map<std::string, uint64_t>::iterator B=logMap.begin(), E=logMap.end();B!=E;++B) {
//         size_t val = B->first.size();
//         SAFE_WRITE(&val, sizeof(size_t), ONE, fp);
//         SAFE_WRITE(B->first.c_str(), sizeof(char), B->first.size(), fp);
//         SAFE_WRITE(&(B->second), sizeof(uint64_t), ONE, fp);
//     }
// #ifndef KEYMAP_NAME_FROM_MODULE
//     // release lock for anyone else
//     if(int r=flock(fd, LOCK_UN)) {
//         errs() << "FETAL ERROR: Failed to unlock file " << KEYMAP_FN << ", err=" << r << "\n";
//         exit(-1);
//     }
// #endif
//     fclose(fp);
//     __unlock();
//     printf("========== Print %s KeyMap finish ===========\n", KEYMAP_FN);
// }
// void PAETT_Utils::printKeyMapStd(std::string m_name) {
//     for(std::unordered_map<std::string, uint64_t>::iterator B=logMap.begin(), E=logMap.end();B!=E;++B) {
//         printf("[%s]: %lx\n",B->first.c_str(),B->second);
//     }
// }

// void PAETT_Utils::readKeyMap(std::string m_name, bool safe_check) {
//     uint64_t r;
//     const size_t ONE = 1;
//     const size_t BUFFSIZE = 500;
//     __lock();
//     FILE* fp = fopen(KEYMAP_FN,"rb");
//     if(fp==NULL && safe_check) {
//         printf("Fetal Error: KeyMap File %s could not open!\n", KEYMAP_FN);
//         __unlock();
//         exit(-1);
//     } else if(fp==NULL) {
//         __unlock();
//         return ;
//     }
//     size_t val; char buff[BUFFSIZE+1];
//     uint64_t data;
//     while(fread(&val, sizeof(size_t), ONE, fp)==ONE) {
//         std::string debug_info = "";
//         while(val>=BUFFSIZE) {
//             SAFE_READ(buff, sizeof(char), BUFFSIZE, fp);
//             val -= BUFFSIZE;
//             buff[BUFFSIZE] = '\0';
//             debug_info += buff;
//         }
//         SAFE_READ(buff, sizeof(char), val, fp);
//         buff[val] = '\0';
//         debug_info += buff;
//         SAFE_READ(&data, sizeof(uint64_t), ONE, fp);
//         logMap[debug_info] = data;
//     }
//     fclose(fp);
//     __unlock();
//     //printKeyMapStd(m_name);
// }
// uint64_t PAETT_Utils::lookupKey(std::string debug_info) {
//     uint64_t key;
//     std::unordered_map<std::string, uint64_t>::iterator it0;
//     if((it0=logMap.find(debug_info))!=logMap.end()) {
//         key = it0->second;
//     } else {
//         key = CCT_INVALID_KEY;
//     }
//     return key;
// }
// uint64_t PAETT_Utils::getInstKeyInt64(uint64_t mid, std::string debug_info) {
//     uint64_t key;
//     std::unordered_map<std::string, uint64_t>::iterator it0;
//     if((it0=logMap.find(debug_info))!=logMap.end()) {
//         key = it0->second;
//     } else {
//         key = MAKE_KEY(mid, keySize);
//         logMap[debug_info]=key;
//         ++keySize;
//     }
//     return key;
// }
std::string PAETT_Utils::loop2string(Loop* loop) {
    std::string s;
    const DebugLoc LoopDbgLoc = loop->getStartLoc();
    raw_string_ostream ss(s);
    LoopDbgLoc.print(ss);
    return std::string("L:") + ss.str();
}
std::string PAETT_Utils::ins2string(Instruction* ins) {
    std::string s;
    const DebugLoc& DbgLoc = ins->getDebugLoc();
    raw_string_ostream ss(s);
    DbgLoc.print(ss);
    return std::string("I:") + ss.str();
}
std::string PAETT_Utils::func2string(Function* F) {
    std::string s;
    const DebugLoc& DbgLoc = F->getEntryBlock().getFirstNonPHIOrDbgOrLifetime()->getDebugLoc();
    raw_string_ostream ss(s);
    DbgLoc.print(ss);
    return std::string("F:") + F->getName().str() + ":" + ss.str();
}

bool PAETT_Utils::isInvalidString(std::string str) {
    if(str==std::string("F:") || str==std::string("L:") || str==std::string("I:")) {
        return true;
    }
    return false;
}

// int PAETT_Utils::getMID(std::string m_name) {
//     int fd = open(INFO_FN,O_RDWR|O_CREAT,S_IRWXU);
//     if(fd==-1) {
//         errs() << "FETAL ERROR: Failed to open file " << INFO_FN << ", err=" << fd << "\n";
//         exit(-1);
//     }
//     // flock will block when the lock is not available
//     if(int r=flock(fd, LOCK_EX)) {
//         errs() << "FETAL ERROR: Failed to lock file " << INFO_FN << ", err=" << r << "\n";
//         exit(-1);
//     }
//     // count logging lines to determing my ID
//     int cc=0; 
//     char buff[500];
//     std::string sn="";
//     while(int s=read(fd, buff, 500)) {
//         for(int i=0;i<s;++i) {
//             // one module occupies a line of the log
//             if(buff[i]=='\n') {
//                 cc++; if(sn==m_name) { goto final; } sn="";
//             } else {
//                 sn+=buff[i];
//             }
//         }
//     }
//     // now write my log to the last of the file
//     write(fd, (m_name+"\n").c_str(), (m_name+"\n").size());
// final:
//     // release lock for anyone else
//     if(int r=flock(fd, LOCK_UN)) {
//         errs() << "FETAL ERROR: Failed to unlock file " << INFO_FN << ", err=" << r << "\n";
//         exit(-1);
//     }
//     close(fd);
//     return cc;
// }

#define FORCE_ALERT_NO_PREHEADER
//#define DEBUG

Instruction* PAETT_Utils::getLoopInsertPrePoint(Loop* lkey) {
    // create enable bbl and insert it before entering this loop
    BasicBlock* header = lkey->getHeader();
    BasicBlock* preHeader = lkey->getLoopPreheader();
    Instruction* res = NULL;
    if(preHeader) {
        res = preHeader->getTerminator();
#ifdef DEBUG
        if (const DebugLoc LoopDbgLoc = lkey->getStartLoc())
            LoopDbgLoc.print(errs());
        else
            // Just print the module name.
            errs() << lkey->getHeader()->getParent()->getParent()->getModuleIdentifier();
        errs() << ": INFO: Preheader found: " << preHeader << " " << preHeader->getParent()->getName().str() << ". Insert instrumentation code into loop preheader: key=" << logHashMap[mid][(uint64_t)F][(uint64_t)lkey] << " " << mid << " " << F << " " << lkey << "\n";
#endif
    } else {
        // no preHeader found, we have to check every loop
        // TODO: Insert a new bbl as its preHeader for lower overhead
        if (const DebugLoc LoopDbgLoc = lkey->getStartLoc())
            LoopDbgLoc.print(errs());
        else
            // Just print the module name.
            errs() << lkey->getHeader()->getParent()->getParent()->getModuleIdentifier() << "\n";
        errs() << ": WARNING: No preheader found: " << header << " " << header->getParent()->getName().str() << ". Insert instrumentation code into loop header (" << loop2string(lkey) << ")\n";
        errs() << "WARNING: instrumentation in loop header will cause heavy overhead. Please run opt --loop-simplify first!\n";
#ifdef FORCE_ALERT_NO_PREHEADER
        assert(0 && "insertInLoop!!!");
#endif
        res = header->getFirstNonPHIOrDbgOrLifetime();
    }
    return res;
}
void PAETT_Utils::getLoopInsertPostPoint(Loop* lkey, std::vector<Instruction*>& res, bool insertInLoop) {
    // create paett_inst_exit function call and insert it after exiting this loop
    std::vector<BasicBlock*> &v = lkey->getBlocksVector();
    SmallVector<BasicBlock*, 4> exitingBlocks;
    std::vector<BasicBlock*> exitBlocks;
    lkey->getExitingBlocks(exitingBlocks);
    for(auto EB=exitingBlocks.begin(), EE=exitingBlocks.end(); EB!=EE; ++EB) {
        BasicBlock* BB = *EB;
        bool inserted = false;
        // exiting cases: return, exit, branch, callbr
        for(BasicBlock::iterator BI = BB->begin(), BE = BB->end(); BI != BE; ++BI) {
            if(dyn_cast<ReturnInst>(&(*BI))) {
                res.push_back(&(*BI));
                inserted=true;
            }
            if(dyn_cast<ResumeInst>(&(*BI))) {
                res.push_back(&(*BI));
                inserted=true;
            }
#ifndef USE_OLD_LLVM
            if(auto *op=dyn_cast<CallBrInst>(&(*BI))) {
                for(unsigned int i=0, n=op->getNumSuccessors();i<n;++i) {
                    auto suc = op->getSuccessor(i);
                    // we do not use lkey->contain(suc) as it will be stuck for unknown reason
                    if(std::find(exitBlocks.begin(),exitBlocks.end(),suc)!=exitBlocks.end()) {
                        inserted=true; // already inserted
                    } else if(std::find(v.begin(),v.end(),suc)==v.end()) {
                        // this is not in the loop
                        res.push_back(&(*(suc->getFirstNonPHIOrDbgOrLifetime())));
                        exitBlocks.push_back(suc);
                        inserted=true;
                    }
                }
            }
#endif
            if(auto *op=dyn_cast<InvokeInst>(&(*BI))) {
                auto unwind = op->getUnwindDest();
                inserted=true;
// #ifdef USE_OLD_LLVM
                if(std::find(exitBlocks.begin(),exitBlocks.end(),unwind)==exitBlocks.end()) {
                    res.push_back(&(*(unwind->getFirstInsertionPt())));
                    exitBlocks.push_back(unwind);
                }
// #else
//                 Instruction* unw = &(*(unwind->getTerminator()));
//                 for(unsigned int i=0, n=unw->getNumSuccessors();i<n;++i) {
//                     auto suc = unw->getSuccessor(i);  
//                     if(std::find(exitBlocks.begin(),exitBlocks.end(),suc)==exitBlocks.end()) {
//                         res.push_back(&(*(suc->getFirstInsertionPt())));
//                         exitBlocks.push_back(suc);
//                     }
//                 }
// #endif
                // auto normal = op->getNormalDest();
                // if(std::find(exitBlocks.begin(),exitBlocks.end(),normal)==exitBlocks.end()) {
                //     res.push_back(&(*(normal->getFirstInsertionPt())));
                //     exitBlocks.push_back(normal);
                // }
            }
            if(auto *op=dyn_cast<BranchInst>(&(*BI))) {
                if(insertInLoop) {
                    res.push_back(&(*BI));
                    inserted=true;
                } else {
                    for(unsigned int i=0, n=op->getNumSuccessors();i<n;++i) {
                        auto suc = op->getSuccessor(i);
                        // we do not use lkey->contain(suc) as it will be stuck for unknown reason
                        if(std::find(exitBlocks.begin(),exitBlocks.end(),suc)!=exitBlocks.end()) {
                            inserted=true; // already inserted
                        } else if(std::find(v.begin(),v.end(),suc)==v.end()) {
                            // this is not in the loop and it is not handled yet
                            res.push_back(&(*(suc->getFirstNonPHIOrDbgOrLifetime())));
                            exitBlocks.push_back(suc);
                            inserted=true;
                        }
                    }
                }
            }
            if(auto *op=dyn_cast<SwitchInst>(&(*BI))) {
                if(insertInLoop) {
                    res.push_back(&(*BI));
                    inserted=true;
                } else {
                    for(unsigned int i=0, n=op->getNumSuccessors();i<n;++i) {
                        auto suc = op->getSuccessor(i);
                        // we do not use lkey->contain(suc) as it will be stuck for unknown reason
                        if(std::find(exitBlocks.begin(),exitBlocks.end(),suc)!=exitBlocks.end()) {
                            inserted=true; // already inserted
                        } else if(std::find(v.begin(),v.end(),suc)==v.end()) {
                            // this is not in the loop
                            res.push_back(&(*(suc->getFirstNonPHIOrDbgOrLifetime())));
                            exitBlocks.push_back(suc);
                            inserted=true;
                        }
                    }
                }
            }
        } // end iterate for instructions in bbl
        // now special case already handled, handle common case
        // create & insert basic block as successor of exiting blocks 
        assert(inserted && "insertInstrumentationCalls: Unknown case happened!");
    }
}