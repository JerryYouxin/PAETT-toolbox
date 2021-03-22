#include "common.h"
#include "config.h"
#include <unordered_map>
#include <vector>
// for file control
#include <sys/file.h>
#include <unistd.h>
#include <algorithm>
#include <string>

#define GET_RESPTR_CONT(res,NAME) res->r##NAME
#define DEFINE_RES_CONT(TYPE,NAME) TYPE r##NAME

namespace CMDModel {
    struct Log_t {
        uint64_t BR_NTK;
        uint64_t LD_INS;
        uint64_t L2_ICR;
        uint64_t BR_MSP; 
        uint64_t RES_STL;
        uint64_t SR_INS; // PEBS
        uint64_t L2_DCR; // PEBS
    };
    struct Res_t {
        DEFINE_RES_CONT(uint64_t,dsize);
        DEFINE_RES_CONT(double*,data);
        static void log2res(Log_t* log, Res_t* res) {
            GET_RESPTR_CONT(res,dsize) = 7;
            double* data = (double*)malloc(sizeof(double)*7);
            data[0] = log->BR_NTK;
            data[1] = log->LD_INS;
            data[2] = log->L2_ICR;
            data[3] = log->BR_MSP;
            data[4] = log->RES_STL;
            data[5] = log->SR_INS;
            data[6] = log->L2_DCR;
            // Filter too small values
            const double threshold = 1000;
            bool filter = true;
            for(int i=0;i<7;++i) {
                filter &= (data[i]<threshold);
            }
            if(filter) {
                for(int i=0;i<7;++i) {
                    data[i]=0.0;
                }
            }
            //printf("log2res: %ld %ld %ld %ld %ld %ld %ld => %lf %lf %lf %lf %lf %lf %lf\n",
            //    log->BR_NTK, log->LD_INS, log->L2_ICR, log->BR_MSP, log->RES_STL, log->SR_INS, log->L2_DCR,
            //    data[0], data[1], data[2], data[3], data[4], data[5], data[6]);
            GET_RESPTR_CONT(res,data) = data;
        }
        static void log2res(uint64_t* log, uint64_t* res) {
            log2res((Log_t*)log, (Res_t*)res);
        }
    };
}

#include "CallingContextTree.h"
#include "CCTRes.h"
#define FREQMOD_CALL_THRESHOLD 0.001

std::unordered_map<uint64_t, std::string> keyMap;
void readKeyMap() {
    uint64_t r;
    const size_t ONE = 1;
    const size_t BUFFSIZE = 500;
    FILE* fp = fopen(KEYMAP_FN".0","r");
    if(fp==NULL) {
        printf("Fetal Error: KeyMap File %s could not open!\n", KEYMAP_FN".0");
        exit(-1);
    }
    CallingContextLog::readKeyString(fp, keyMap);
    fclose(fp);
}

static bool compareByTime(CCTRes* a, CCTRes* b) {
            return a->data.time > b->data.time;
        }

namespace {
#include "freqmod.h"
    // frequency modifications are listed as commands
    typedef struct {
        uint64_t core, uncore, thread;
    } freqPair;
    typedef struct {
        uint64_t key; // key value of this command, indicates the location (Loop, Function) of this modification command
        freqPair pre;  // frequency adjust before enter
        freqPair post; // frequency adjust after exit
    } FreqCommand_t;
    bool isInvalidFreqCommand(FreqCommand_t& c) { return c.pre.core==0 && c.pre.uncore==0 && c.pre.thread==0 && c.post.core==0 && c.post.uncore==0 && c.post.thread==0; }
    typedef std::unordered_map<uint64_t, FreqCommand_t> FreqCommandMap_t; 
    template<class Res_t>
    class ModelAdapterBaseImpl {
        public:
        virtual void getFreqPair(uint64_t key, Res_t* prof, uint64_t* coreFreq, uint64_t* uncoreFreq, uint64_t* thread) = 0;
    };
    template<class Res_t>
    class Transformer : public TransformerBase<DataLog, DataLog> {
        public:
        // overload interface method to transform CCT data
        void handler(uint64_t key, DataLog& src, DataLog& dst, bool valid) {
            Res_t res;
#ifdef DEBUG
            printf("Transformer::handler::src = "); src.print();
#endif
            if(src.eventData==NULL) {
                //dst.time=0; dst.valid=false; dst.core=0; dst.uncore=0;
                dst.cycle = 0; dst.ncall=1; dst.eventData = 0; dst.size = 0;
#ifdef DEBUG
                printf("-> invalid NULL\n");
#endif
                return;
            }
            assert(src.ncall!=0);
            // dst.time = T_tot*(src.cycle/(double)Cyc_tot); // total call time
            //dst.time = src.cycle;
            dst.cycle = src.cycle;
            //printf("**** Actual UOPS=%lf G\n",(double)((double)res.rUOP*1e5/1e9)/dst.time);
            dst.ncall= src.ncall;
            dst.active_thread = src.active_thread;
            dst.size = sizeof(Res_t)/sizeof(uint64_t);
            dst.eventData = (uint64_t*)malloc(dst.size*sizeof(uint64_t));
            // dst.valid = true; // default valid state
            if (valid) {
                Res_t::log2res(src.eventData, dst.eventData);
            } else {
                memset(dst.eventData, 0, dst.size*sizeof(uint64_t));
            }
#ifdef DEBUG
            printf("-> "); Res_t::print(&res); printf("\n");
#endif
            //caller->getFreqPair(key, &res, &(dst.core), &(dst.uncore), &(dst.thread));
        }
        static Transformer* getTransformer(double T, uint64_t Cyc, ModelAdapterBaseImpl<Res_t>* MA) {
            return new Transformer(T, Cyc, MA);
        }
        private:
        Transformer(double T, uint64_t Cyc, ModelAdapterBaseImpl<Res_t>* MA) {
            T_tot = T; Cyc_tot = Cyc==0?1:Cyc; caller=MA;
        }
        double T_tot;
        uint64_t Cyc_tot;
        ModelAdapterBaseImpl<Res_t>* caller;
    };
    // TODO: This template is quite duplicated but I did not find better solution. 
    template<class Res_t>
    class ModelAdapterBase : public ModelAdapterBaseImpl<Res_t> {
        public:
        ModelAdapterBase() { initialized=false; }
        void init() {
            if(initialized) return;
            initialized = true;
            // TODO: read global value from generated config file
            //uint64_t us;
            FILE* fp = fopen(PAETT_GENERAL_PROF_FN, "r");
            if(fp==NULL) {
                printf("Profile: %s not Found!\n", PAETT_GENERAL_PROF_FN);
                exit(1);
            }
            isCached();
            //fscanf(fp, "%ld", &us);
            std::vector<uint64_t> us_multi;
            uint64_t _us;
            while(fscanf(fp, "%ld", &_us)!=EOF) {
                us_multi.push_back(_us);
            }
            assert(us_multi.size()>0);
            fclose(fp);
            printf("\nINFO: READ profile: %lu us (%lf s)\n",us_multi[0],(double)us_multi[0] / 1e6);
            printf("INFO: profiled thread count: %u threads\n",us_multi.size());
            readKeyMap(); // read key map from profile
            openLog();
            for(int i=0, n=us_multi.size();i<n;++i) {
                // reconstruct root CCTLog from profile
                CallingContextLog* logRoot = CallingContextLog::read(MAKE_THREAD_PROF_FN(PAETT_PERF_INSTPROF_FN, i));
                // Get total Cycle number from log
                std::vector<DataLog> logList;
                fprintf(LOG,"\n============ CCTLog Created ============\n");
                CallingContextLog::print(logRoot, LOG);
                logRoot->getPreOrderList(logList);
                double T=(double)us_multi[i] / 1e6;
                uint64_t Cyc=0;
                for(auto B=logList.begin(), E=logList.end();B!=E;++B) {
                    Cyc += B->cycle;
                }
                // Prune short-running regions from the CCT first
                pruneShortrunningNodes(logRoot);
                // convert DataLog CCT tree to FreqData CCT tree by Power Model
                Transformer<Res_t>* transformer = Transformer<Res_t>::getTransformer(T,Cyc,this);
                CallingContextLog* resRoot = createCCTfrom<DataLog, DataLog>(logRoot, transformer);
                logList.clear();
                resRoot->getPreOrderList(logList);
                assert(!logList.empty());
                std::vector<FreqData> freqList;
                getFreqListFromResList(freqList, logList);
                assert(freqList.size()==logList.size());
                CCTRes* root = createCCTfromPreOrderList(resRoot, freqList);
                delete transformer;
                fprintf(LOG, "\n============ CCTRes Created ============\n");
                CCTRes::print(root, LOG);
                // standardize the frequency before optimization to make sure the CCT inheritance of the frequency is correct
                stdCCTFreq(root);
                fprintf(LOG, "\n============ CCTRes Standardized ============\n");
                CCTRes::print(root, LOG);
                // optimize the CCT Tree due to cost-model
                optimizeCCT(root);
                fprintf(LOG, "\n============ CCTRes Optimized ============\n");
                CCTRes::print(root, LOG);
                // Construct (Merge) FreqCommandMap from FreqData CCT tree
                constructFreqCommandMap(root);
                // Debug output
                printAllFreqCommand(LOG);
                printValidRegionCoverage(root);
                // output cache file
                CallingContextLog::free(logRoot);
                CallingContextLog::free(resRoot);
                CCTRes::free(root);
            }
            closeLog();
            writeFreqCommandMapToCache();
            safe_close(cache);
        }

        void getFreqListFromResList(std::vector<FreqData> &freqList, std::vector<DataLog> &logList) {
            // generate test dataset input for model with logList
            int n = logList.size();
            std::stringstream s;
            for(int i=0; i<n; ++i) {
                Res_t* res = (Res_t*)(logList[i].eventData);
                if(res==NULL) { s << "0 0 0 0 0 0 0\n"; continue; }
                uint64_t dsize = GET_RESPTR_CONT(res, dsize);
                double* data = GET_RESPTR_CONT(res, data);
                if(data==NULL||dsize==0) { s << "0 0 0 0 0 0 0\n"; continue; }
                s << data[0];
                for(int i=1;i<dsize;++i) {
                    s << " " << data[i];
                }
                s << "\n";
            }
            FILE* fp = fopen("batched_input.in","w");
            fprintf(fp, "%s",s.str().c_str());
            fclose(fp);
            std::stringstream comm;
            std::string _cmd = "getOptFreq_batched";
            comm << _cmd << " batched_input.in";
            printf("Launch: %s ... \n",comm.str().c_str()); fflush(stdout);
                
            fp = popen(comm.str().c_str(), "r");
            if (NULL==fp) {
                printf("Error!!\n");
                exit(1);
                return; // silent failure.
            }
            pclose(fp);
            fp = fopen("batched_freq.out","r");
            assert(fp);
            double core, uncore; uint64_t thread;
            while(EOF!=fscanf(fp, "%lf %lf %ld\n",&core, &uncore, &thread)) {
                //printf("Returned %lf %lf %ld\n",core, uncore, thread); fflush(stdout);
                FreqData fdata;
                fdata.core   = MAKE_CORE_VALUE_FROM_FREQ(core);
                fdata.uncore = MAKE_UNCORE_VALUE_BY_FREQ(uncore*10);
                fdata.thread = thread;
                fdata.time   = logList[freqList.size()].cycle;
                fdata.ncall  = logList[freqList.size()].ncall;
                fdata.valid  = true;
                freqList.push_back(fdata);
            }
            fclose(fp);
        }

        FreqCommand_t getFreqCommand(uint64_t key) {
            assert(initialized);
            FreqCommandMap_t::iterator it = freqCommandMap.find(key);
            if(it!=freqCommandMap.end()) {
                return it->second;
            } else {
                return {key, {0,0}, {0,0}};
            }
        }
        void printAllFreqCommand(FILE* fp=stdout) {
            assert(initialized);
            fprintf(fp,"\n====== %lu commands constructed ======\n",freqCommandMap.size());
            for(auto B=freqCommandMap.begin(),E=freqCommandMap.end();B!=E;++B) {
                fprintf(fp,"%lx:[key=%lx(%s)]:pre=(%ld, %ld),post=(%ld, %ld)\n",B->first,
                    B->second.key, keyMap[B->second.key].c_str(),
                    B->second.pre.core,B->second.pre.uncore, 
                    B->second.post.core, B->second.post.uncore);
            }
        }
        protected:
        bool initialized;
#ifdef USE_POWER_MODEL_FOR_COST
        double P_core, P_uncore;
#endif
        FILE* LOG;
        const std::string LOG_FN="paett_model.log";
        FILE* safe_open(const char* fn, const char* mode) {
            int fd = open(fn,O_RDWR|O_CREAT,S_IRWXU);
            if(fd==-1) {
                fprintf(stderr, "FETAL ERROR: Failed to open file %s, err=%d\n", fn, fd);
                exit(-1);
            }
            // flock will block when the lock is not available
            if(int r=flock(fd, LOCK_EX)) {
                fprintf(stderr, "FETAL ERROR: Failed to lock file %s, err=%d\n", fn, fd);
                exit(-1);
            }
            return fdopen(fd, mode);
        }
        void safe_close(FILE* fp) {
            int fd = fileno(fp);
            if(int r=flock(fd, LOCK_UN)) {
                fprintf(stderr, "FETAL ERROR: Failed to unlock file %s, err=%d\n", LOG_FN.c_str(), fd);
                exit(-1);
            }
            fclose(fp);
        }
        void openLog() {
            LOG = safe_open(LOG_FN.c_str(), "w");
        }
        void closeLog() {
            safe_close(LOG);
        }
        FILE* cache;
        const std::string CACHE_FN="paett_model.cache";
        bool isCached() {
            cache = safe_open(CACHE_FN.c_str(), "r+");
            int v; // placeholder to check if the cache file is valid or not
            return (fscanf(cache,"%d",&v)!=EOF);
        }
        void enableConcurrentCacheRead() {
            int fd = fileno(cache);
            if(int r=flock(fd, LOCK_UN)) {
                fprintf(stderr, "FETAL ERROR: Failed to unlock file %s, err=%d\n", LOG_FN.c_str(), fd);
                exit(-1);
            }
        }
        // void readFreqCommandMapFromCache() {
        //     FreqCommand_t command;
        //     uint64_t key;
        //     int r0;
        //     while(EOF!=(r0=fscanf(cache, "%lx", &key))) {
        //         fscanf(cache, "%lx",&command.key);
        //         fscanf(cache, "%ld",&command.pre.core);
        //         fscanf(cache, "%ld",&command.pre.uncore);
        //         fscanf(cache, "%ld",&command.pre.thread);
        //         fscanf(cache, "%ld",&command.post.core);
        //         fscanf(cache, "%ld",&command.post.uncore);
        //         fscanf(cache, "%ld",&command.post.thread);
        //         fprintf(stdout,"%lx %lx %ld %ld %ld %ld %ld %ld\n",key, command.key,
        //             command.pre.core,command.pre.uncore, command.pre.thread,
        //             command.post.core, command.post.uncore, command.post.thread);
        //         freqCommandMap[key] = command;
        //     }
        //     printf("Read finish\n");
        // }
        void writeFreqCommandMapToCache() {
            fprintf(cache,"%d ",1); // placeholder to inform the cache file is valid
            for(auto B=freqCommandMap.begin(),E=freqCommandMap.end();B!=E;++B) {
                fprintf(cache,"%lx %s;%ld %ld %ld %ld %ld %ld\n",B->first, keyMap[B->second.key].c_str(),
                    B->second.pre.core,B->second.pre.uncore, B->second.pre.thread,
                    B->second.post.core, B->second.post.uncore, B->second.post.thread);
            }
        }
        FreqCommandMap_t freqCommandMap;
        virtual void optimizeCCT(CCTRes* root) {
            // invalidate redundant frequency nodes first
            pruneRedundantNodes(root);
            // prune costly nodes with overhead-aware energy cost model
            pruneNodesWithCostModel(root);
        }
        virtual bool pruneShortrunningNodes(CallingContextLog* cur) {
            const double OVERHEAD_THRESHOLD = 0.05;
            return pruneCCTWithThreshold(cur, PRUNE_THRESHOLD);
        }
        std::unordered_map<uint64_t, uint64_t> prunedRegion;
        void __pruneNodesAsRegions(CCTRes* cur) {
            for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
                __pruneNodesAsRegions(CB->second);
            }
            if(cur->data.valid) {
                cur->data.valid = (prunedRegion.find(cur->key)==prunedRegion.end());
            }
        }
        // time in us
        void __getValidRegionTime(CCTRes* cur, double* vtime, double* total) {
            if(cur->data.valid) {
                *vtime += cur->data.time;
            }
            *total += cur->data.time;
            for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
                __getValidRegionTime(CB->second, vtime, total);
            }
        }
        void __getSignificantRegions(CCTRes* cur, std::vector<CCTRes*> &list) {
            list.push_back(cur);
            for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
                __getSignificantRegions(CB->second, list);
            }
        }
        void printSignificantRegionRanking(CCTRes* cur) {
            std::vector<CCTRes*> list;
            __getSignificantRegions(cur, list);
            std::sort(list.begin(), list.end(), compareByTime);
            printf("=== Ranking ===\n");
            for(int i=0;i<list.size();++i) {
                printf("%lx: %lf\n",list[i]->key,list[i]->data.time);
            }
            printf("===============\n");
        }
        void printValidRegionCoverage(CCTRes* cur) {
            double vtime, total;
            __getValidRegionTime(cur, &vtime, &total);
            printf("Valid Time: %.1lf us, Total Time: %.1lf us, Coverage: %.2lf %%\n",vtime, total, vtime/total);
            printSignificantRegionRanking(cur);
        }
        virtual void __pruneNodesWithCostModel(CCTRes* cur) {
            // try to prune its children first to get more accurate time estimation for this node
            for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
                __pruneNodesWithCostModel(CB->second);
            }
            // get actual time assumed to be executed exactly in this function (exclude his *valid* children's)
            double time = cur->data.time;
            for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
                if(!(CB->second->data.valid)) {
                    time += CB->second->data.time;
                }
            }
            // now update the time
            cur->data.time = time;
            time /= cur->data.ncall; // per call time
            // if this node is already pruned (invalid), skip the analysis.
            if(!(cur->data.valid)) {
                prunedRegion[cur->key] = 0;
                return;
            }
            // simple and aggresive pruning methodology
            // We define acceptable overhead control threshold (5%)
            #define OVERHEAD_THRESHOLD 0.05
            double uncore = DECODE_MAX_FREQ_FROM_UNCORE_VALUE(cur->data.uncore);
            double core = DECODE_FREQ_FROM_CORE_VALUE(cur->data.core);
            if(core!=0 && uncore!=0 && OVERHEAD/time >= OVERHEAD_THRESHOLD) {
                cur->data.valid = false;
            } else if (core==0 && uncore!=0 && OVERHEAD/time >= OVERHEAD_THRESHOLD) {
                cur->data.valid = false;
            } else if (core!=0 && uncore==0 && OVERHEAD/time >= OVERHEAD_THRESHOLD) {
                cur->data.valid = false;
            } else if (core==0 && uncore==0) {
                cur->data.valid = false;
            }
            if(!(cur->data.valid)) {
                prunedRegion[cur->key] = 0;
            }
        }
        void pruneNodesWithCostModel(CCTRes* cur) {
            prunedRegion.clear();
            __pruneNodesWithCostModel(cur);
            __pruneNodesAsRegions(cur);
        }
        void pruneRedundantNodes(CCTRes* cur) {
            for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
                pruneRedundantNodes(CB->second);
            }
            if(cur->parent!=0 && cur->parent->data.valid && cur->parent->data.core==cur->data.core && cur->parent->data.uncore==cur->data.uncore) {
                cur->data.valid = false; // prune if the child's command is same as its parent's
            }
        }
        void constructFreqCommandMap(CCTRes* cur) {
            if(cur->data.valid) {
                FreqCommand_t command = {cur->key, {cur->data.core, cur->data.uncore}, {0,0}};
                if(cur->parent!=0 && cur->data.core!=0) {
                    command.post.core  = cur->parent->data.core;
                }
                if(cur->parent!=0 && cur->data.uncore!=0) {
                    command.post.uncore= cur->parent->data.uncore; 
                }
                // TODO: CCT-centered freqmod
                // now, we merge different cct's core & uncore to region-view single command
                auto it = freqCommandMap.find(cur->key);
                if(it!=freqCommandMap.end()) {
                    printf("Warning: Merging commands from different CCT\n");
                    it->second.pre.core = std::max(it->second.pre.core, command.pre.core);
                    it->second.pre.uncore = std::max(it->second.pre.uncore, command.pre.uncore);
                    it->second.post.core = std::max(it->second.post.core, command.post.core);
                    it->second.post.uncore = std::max(it->second.post.uncore, command.post.uncore);
                } else {
                    freqCommandMap[cur->key] = command;
                }
            }
            for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
                constructFreqCommandMap(CB->second);
            }
        }
        // iterate with post order to standardize freq according to its CCT
        void stdCCTFreq(CCTRes* cur) {
            if(cur->children.empty()) {
                cur->data.valid = (cur->data.core!=0 || cur->data.uncore!=0);
                return;
            }
            uint64_t core   = cur->data.core;
            uint64_t uncore = cur->data.uncore;
            // a node's freq must not be smaller than its children's
            for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
                stdCCTFreq(CB->second);
            }
            if(core==0) {
                for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
                    core = std::max(core, CB->second->data.core);
                }
            }
            if(uncore==0) {
                for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
                    uncore = std::max(uncore, CB->second->data.uncore);
                }
            }
            cur->data.core = core;
            cur->data.uncore = uncore;
            cur->data.valid = (core!=0 || uncore!=0);
        }
    };

    class CMDModelAdapter : public ModelAdapterBase<CMDModel::Res_t> {
        std::string _cmd;
        // override function to get the proper core, uncore pair
        public:
        CMDModelAdapter(std::string cmd="getOptFreq") : ModelAdapterBase<CMDModel::Res_t>(), _cmd(cmd) {}
        virtual void getFreqPair(uint64_t key, CMDModel::Res_t* prof, uint64_t* coreFreq, uint64_t* uncoreFreq, uint64_t* thread) override {
            // uint64_t dsize = GET_RESPTR_CONT(prof, dsize);
            // double* data = GET_RESPTR_CONT(prof, data);
            // double core, uncore;
            // std::stringstream s;
            // s << _cmd << " " << key;
            // bool skip = true;
            // for(int i=0;i<dsize;++i) {
            //     s << " " << data[i];
            //     skip = skip && (data[i]==0);
            // }
            // if(!skip) {
            //     printf("Launch: %s ... \n",s.str().c_str()); fflush(stdout);
            //     FILE *fp = popen(s.str().c_str(), "r");
            //     if (NULL==fp)
            //         return; // silent failure.

            //     char buf[2*PATH_MAX] = {0};
            //     if (NULL != fgets(buf, 2*PATH_MAX, fp)){
            //         std::stringstream ss(buf);
            //         ss >> core >> uncore >> (*thread);
            //     }
            //     pclose(fp);
            //     printf("Returned %lf %lf %ld\n",core, uncore, *thread); fflush(stdout);
            //     *coreFreq = MAKE_CORE_VALUE_FROM_FREQ(core);
            //     *uncoreFreq = MAKE_UNCORE_VALUE_BY_FREQ(uncore*10);
            // } else {
            //     *coreFreq = 0;
            //     *uncoreFreq = 0;
            //     *thread = 0;
            // }
            return ;
        }
    };
}
int main() {
    CMDModelAdapter m;
    m.init();
    return 0;
}