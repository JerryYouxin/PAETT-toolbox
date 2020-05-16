#include "libpaett_freqmod.cpp"

#include "CCTFreqCommand.h"

#define LIBPAETT_INST_LOGFN "libpaett_inst.log"
// C-style interfaces for lib call
extern "C" void PAETT_print();
extern "C" void PAETT_inst_init();
extern "C" void PAETT_inst_enter(uint64_t key); // key = MAKE_KEY(mid, l_key)
extern "C" void PAETT_inst_exit(uint64_t key);
extern "C" void PAETT_inst_thread_init(uint64_t key); // key = MAKE_KEY(mid, l_key)
extern "C" void PAETT_inst_thread_fini(uint64_t key);
extern "C" void PAETT_inst_finalize();

CCTFreqCommand* root=NULL;
int danger = 0;
FILE* FLOG;

void PAETT_print() {
    printf("\n=========== USING PAETT CCT-AWARE FREQMOD ============\n");
}

void PAETT_inst_init() {
    PAETT_init();
    char* envPath = getenv("PAETT_CCT_FREQUENCY_COMMAND_FILE");
    if(envPath==NULL) {
        root = readCCTFreqCommand(LIBPAETT_INST_LOGFN);
    } else {
        root = readCCTFreqCommand(envPath);
    }
    if(root) {
        printf("Configured Frequency Command CCT:\n");
        CCTFreqCommand::print(root);
    } else {
        printf("No frequency command CCT configuration found\n");
    }
    FLOG = fopen("libpaett_freqmod_cct.log","w");
    // fprintf(FLOG, "libpaett_freqmod_cct initialized: %d\n", root!=NULL); fflush(FLOG);
}

void PAETT_inst_exit(uint64_t key) {
    // fprintf(FLOG,"Exit %ld: danger=%d, root=%p\n", key, danger, root); fflush(FLOG);
    if(danger || root==NULL) return;
    root = root->parent;
    if(root->data.core!=0) {
        // fprintf(FLOG,"Exit %ld: Core => %ld\n", key, root->data.core); fflush(FLOG);
        PAETT_modCoreFreq(root->data.core);
    }
    if(root->data.uncore!=0) {
        // fprintf(FLOG,"Exit %ld: Uncore => %ld\n", key, root->data.uncore); fflush(FLOG);
        PAETT_modUncoreFreq(root->data.uncore);
    }
}

void PAETT_inst_enter(uint64_t key) {
    // fprintf(FLOG,"Enter %ld: danger=%d, root=%p\n", key, danger, root); fflush(FLOG);
    if(danger || root==NULL) return;
    root = root->getOrInsertChild(key);
    if(root->data.core!=0) {
        // fprintf(FLOG,"Enter %ld: Core => %ld\n", key, root->data.core); fflush(FLOG);
        PAETT_modCoreFreq(root->data.core);
    }
    if(root->data.uncore!=0) {
        // fprintf(FLOG,"Enter %ld: Uncore => %ld\n", key, root->data.uncore); fflush(FLOG);
        PAETT_modUncoreFreq(root->data.uncore);
    }
}

void PAETT_inst_thread_init(uint64_t key) {
    PAETT_inst_enter(key);
    if(root->data.thread!=0) {
        PAETT_modOMPThread(root->data.thread);
    }
    ++danger;
}

void PAETT_inst_thread_fini(uint64_t key) {
    --danger;
    PAETT_inst_exit(key);
    if(root->data.thread!=0) {
        PAETT_modOMPThread(root->data.thread);
    }
}

void PAETT_inst_finalize() {
    if(root!=NULL) {
        root->clear();
        CCTFreqCommand::free(root);
        root = NULL;
    }
    PAETT_finalize();
    // fprintf(FLOG, "Finish\n"); fflush(FLOG);
    fclose(FLOG);
}