#define LIBPAETT_CCT_FREQFILE "paett_freqmod.cct"
#ifndef USE_NAMESPACE
#include "libpaett_freqmod.cpp"
#include "CCTFreqCommand.h"
// C-style interfaces for lib call
extern "C" void PAETT_print();
extern "C" void PAETT_inst_init();
extern "C" void PAETT_inst_enter(uint64_t key); // key = MAKE_KEY(mid, l_key)
extern "C" void PAETT_inst_exit(uint64_t key);
extern "C" void PAETT_inst_thread_init(uint64_t key); // key = MAKE_KEY(mid, l_key)
extern "C" void PAETT_inst_thread_fini(uint64_t key);
extern "C" void PAETT_inst_finalize();
#define FUNCNAME(func) func
#else
namespace freqmod_cct {
#include "libpaett_freqmod.cpp"
#include "CCTFreqCommand.h"
#define FUNCNAME(func) __FREQMOD_CCT_##func
#endif

CCTFreqCommand* root=NULL;
int danger = 0;
FILE* FLOG;

void FUNCNAME(PAETT_print)() {
    printf("\n=========== USING PAETT CCT-AWARE FREQMOD ============\n");
}

int64_t data[] = {
    1,-1,1900000,4883,12,
    2,-1,1,2200000,4626,14,
    3,-1,1,2,2200000,4626,14,
    4,-1,1,2,3,2100000,4369,20,
    2,-1,4,2100000,4626,14,
    3,-1,4,5,2100000,4626,14,
    4,-1,4,5,6,2100000,4626,1,
    2,-1,8,1900000,4883,20,
    3,-1,8,9,2000000,4883,20,
    3,-1,8,12,2200000,4369,20,
    2,-1,14,2000000,4883,18,
    2,-1,15,2200000,4369,20,
    3,-1,15,16,2000000,2313,20,
    4,-1,15,16,17,2000000,4883,12,
    4,-1,15,16,5,2100000,4883,16,
    4,-1,15,16,19,2200000,4369,20,
    5,-1,15,16,19,9,1900000,4883,20,
    5,-1,15,16,19,12,1000000,2313,20,
    6,-1,15,16,19,12,13,2200000,2313,20,
    2,-1,20,2000000,4883,20
};

void FUNCNAME(PAETT_inst_init)() {
    PAETT_init();
    char* envPath = getenv("PAETT_CCT_FREQUENCY_COMMAND_FILE");
    if(envPath==NULL) {
        root = readCCTFreqCommand(LIBPAETT_CCT_FREQFILE);
    } else {
        root = readCCTFreqCommand(envPath);
    }
    // root = parseCCTFreqCommandDesc(data, sizeof(data)/sizeof(uint64_t));
    if(root) {
        printf("Configured Frequency Command CCT:\n");
        CCTFreqCommand::print(root);
        if(root->data.thread!=0) {
            PAETT_modOMPThread(root->data.thread);
        }
        PAETT_modCoreFreq(root->data.core);
        PAETT_modUncoreFreq(root->data.uncore);
    } else {
        printf("No frequency command CCT configuration found\n");
    }
    // FLOG = fopen("libpaett_freqmod_cct.log","w");
    // fprintf(FLOG, "libpaett_freqmod_cct initialized: %d\n", root!=NULL); fflush(FLOG);
}

void FUNCNAME(PAETT_inst_exit)(uint64_t key) {
    // fprintf(FLOG,"Exit %ld: danger=%d, root=%p\n", key, danger, root); fflush(FLOG);
    if(danger || root==NULL) return;
    root = root->parent;
    if(root->data.thread!=0) {
        PAETT_modOMPThread(root->data.thread);
    }
    if(root->data.core!=0) {
        // fprintf(FLOG,"Exit %ld: Core => %ld\n", key, root->data.core); fflush(FLOG);
        PAETT_modCoreFreq(root->data.core);
    }
    if(root->data.uncore!=0) {
        // fprintf(FLOG,"Exit %ld: Uncore => %ld\n", key, root->data.uncore); fflush(FLOG);
        PAETT_modUncoreFreq(root->data.uncore);
    }
}

void FUNCNAME(PAETT_inst_enter)(uint64_t key) {
    // fprintf(FLOG,"Enter %ld: danger=%d, root=%p\n", key, danger, root); fflush(FLOG);
    if(danger || root==NULL) return;
    root = root->getOrInsertChild(key);
    if(root->data.thread!=0) {
        PAETT_modOMPThread(root->data.thread);
    }
    if(root->data.core!=0) {
        // fprintf(FLOG,"Enter %ld: Core => %ld\n", key, root->data.core); fflush(FLOG);
        PAETT_modCoreFreq(root->data.core);
    }
    if(root->data.uncore!=0) {
        // fprintf(FLOG,"Enter %ld: Uncore => %ld\n", key, root->data.uncore); fflush(FLOG);
        PAETT_modUncoreFreq(root->data.uncore);
    }
}

void FUNCNAME(PAETT_inst_thread_init)(uint64_t key) {
    FUNCNAME(PAETT_inst_enter)(key);
    ++danger;
}

void FUNCNAME(PAETT_inst_thread_fini)(uint64_t key) {
    --danger;
    FUNCNAME(PAETT_inst_exit)(key);
}

void FUNCNAME(PAETT_inst_finalize)() {
    if(root!=NULL) {
        root->clear();
        CCTFreqCommand::free(root);
        root = NULL;
    }
    PAETT_finalize();
    // fprintf(FLOG, "Finish\n"); fflush(FLOG);
    // fclose(FLOG);
}

#ifdef USE_NAMESPACE
}
#endif