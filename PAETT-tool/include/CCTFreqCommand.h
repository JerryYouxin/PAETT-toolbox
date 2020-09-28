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
    void print(FILE* fp=stdout) { fprintf(fp, "(%ld, %ld, %ld)", core, uncore, thread); }
    void clear() { core=0; uncore=0; thread=0; }
};

typedef CallingContextTree<FreqCommandData> CCTFreqCommand;

/* .cct format example
Enter 1 0 -1 ...
  Enter 2 0 -1 ...
    Enter 3 0 -1 ...
        Enter 4 0 -1 ...
            Enter 5 0 0 2400000 1560 18
            Enter 5 1 1 ...
            Enter 5 2 -1 ...
            Exit
        Exit
    Exit
Exit
*/
CCTFreqCommand* readCCTFreqCommand(const char* fn) {
    double s = omp_get_wtime();
    CCTFreqCommand* root = CCTFreqCommand::get();
    double e = omp_get_wtime();
    printf("get time %lf\n", e-s);
    FILE* fp = fopen(fn, "r");
    if(fp==NULL) {
        printf("CCT Frequency Command File: %s could not open!\n", fn);
        return NULL;
    }
    CCTFreqCommand* p = root;
    char command[10];
    while(EOF!=fscanf(fp, "%s", command)) {
        if(strcmp(command, "Enter")==0) {
            uint64_t key;
            fscanf(fp, "%ld", &key);
            p = p->getOrInsertChild(key);
            fscanf(fp, "%ld", &(p->start_index));
            fscanf(fp, "%ld", &(p->end_index));
            // make sure the next get will insert a new node
            p->cur_index = p->end_index;
            fscanf(fp, "%ld", &(p->data.core));
            fscanf(fp, "%ld", &(p->data.uncore));
            fscanf(fp, "%ld", &(p->data.thread));
            assert(p->data.thread>=0 && p->data.thread<=NCPU);
        } else if(strcmp(command, "Exit")==0) {
            p = p->parent;
        } else {
            printf("Unknown command from %s: %s\n", fn, command);
            exit(-1);
        }
    }
    root->reset();
    // assert(root->children[0].first==-1);
    return root->children[0].second;
}

// ascii encoding
// <# of CCT region> <CCT> <core> <uncore> <thread>
// CCT: path;to;region
// region: a unique integer value
// CCTFreqCommand* readCCTFreqCommand(const char* fn) {
//     CCTFreqCommand* root = CCTFreqCommand::get();
//     FILE* fp = fopen(fn, "r");
//     if(fp==NULL) {
//         printf("CCT Frequency Command File: %s could not open!\n", fn);
//         return NULL;
//     }
//     uint64_t Nreg;
//     while(EOF!=fscanf(fp, "%ld", &Nreg)) {
//         CCTFreqCommand* p = root;
//         for(uint64_t i=0;i<Nreg;++i) {
//             uint64_t key;
//             fscanf(fp, "%ld", &key);
//             p = p->getOrInsertChild(key);
//         }
//         fscanf(fp, "%ld", &(p->data.core));
//         fscanf(fp, "%ld", &(p->data.uncore));
//         fscanf(fp, "%ld", &(p->data.thread));
//     }
//     // assert(root->children[0].first==-1);
//     return root->children[0].second;
// }

// CCTFreqCommand* parseCCTFreqCommandDesc(uint64_t* cct_desc, uint64_t n) {
//     if(cct_desc==0 || n<=0) return NULL;
//     CCTFreqCommand* root = CCTFreqCommand::get();
//     uint64_t k=0;
//     while(k<n) {
//         uint64_t Nreg = cct_desc[k++];
//         CCTFreqCommand* p = root;
//         for(uint64_t i=0;i<Nreg;++i) {
//             uint64_t key = cct_desc[k++];
//             p = p->getOrInsertChild(key);
//         }
//         p->data.core = cct_desc[k++];
//         p->data.uncore = cct_desc[k++];
//         p->data.thread = cct_desc[k++];
//     }
//     // assert(root->children[0].first==-1);
//     printf("USE NEW\n");
//     return root->children[0].second;
// }