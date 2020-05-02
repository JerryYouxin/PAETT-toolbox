#pragma once
#include <string>
#include <vector>
#include <unordered_map>
#include "llvm/IR/Function.h"
#include "llvm/IR/Instruction.h"
#include "llvm/Analysis/LoopInfo.h"
class PAETT_Utils {
    public:
    void printKeyMap(std::string m_name);
    void readKeyMap(std::string m_name, bool safe_check=true);
    void printKeyMapStd(std::string m_name);
    uint64_t lookupKey(std::string debug_info);
    uint64_t getInstKeyInt64(uint64_t mid, std::string debug_info);
    std::string loop2string(llvm::Loop* loop);
    std::string ins2string(llvm::Instruction* ins);
    std::string func2string(llvm::Function* F);
    int getMID(std::string m_name);
    llvm::Instruction* getLoopInsertPrePoint(llvm::Loop* lkey);
    void getLoopInsertPostPoint(llvm::Loop* lkey, std::vector<llvm::Instruction*>& res, bool insertInLoop=false);
    PAETT_Utils();
    // private:
    uint64_t keySize;
    std::unordered_map<std::string, uint64_t> logMap;
};