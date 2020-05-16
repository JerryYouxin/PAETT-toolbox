#include "CallingContextTree.h"

struct FreqCommandData : DataBase {
    uint64_t core;
    uint64_t uncore;
    uint64_t thread;
    void fprint(FILE* fp) {
        uint64_t r;
        const uint64_t ONE=1;
        SAFE_WRITE(&core, sizeof(uint64_t), ONE, fp);
        SAFE_WRITE(&uncore, sizeof(uint64_t), ONE, fp);
        SAFE_WRITE(&thread, sizeof(uint64_t), ONE, fp);
    }
    void read(FILE* fp) { 
        uint64_t r;
        const uint64_t ONE=1;
        SAFE_READ(&core, sizeof(uint64_t), ONE, fp);
        SAFE_READ(&uncore, sizeof(uint64_t), ONE, fp);
        SAFE_READ(&thread, sizeof(uint64_t), ONE, fp);
    }
    void print(FILE* fp=stdout) { fprintf(fp, "(%ld, %ld)", core, uncore); }
    void clear() { core=0; uncore=0; }
};

typedef CallingContextTree<FreqCommandData> CCTFreqCommand;

// ascii encoding
// <# of CCT region> <CCT> <core> <uncore> <thread>
// CCT: path;to;region
// region: a unique integer value
CCTFreqCommand* readCCTFreqCommand(const char* fn) {
    CCTFreqCommand* root = CCTFreqCommand::get();
    FILE* fp = fopen(fn, "r");
    uint64_t Nreg;
    while(EOF!=fscanf(fp, "%ld", &Nreg)) {
        CCTFreqCommand* p = root;
        for(uint64_t i=0;i<Nreg;++i) {
            uint64_t key;
            fscanf(fp, "%ld", &key);
            p = p->getOrInsertChild(key);
        }
        fscanf(fp, "%ld", &(p->data.core));
        fscanf(fp, "%ld", &(p->data.uncore));
        fscanf(fp, "%ld", &(p->data.thread));
    }
    return root;
}