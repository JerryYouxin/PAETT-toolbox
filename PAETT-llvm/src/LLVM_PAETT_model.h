#include "common.h"
#include <unordered_map>
#include <vector>
// for file control
#include <sys/file.h>
#include <unistd.h>
#include <string>

namespace {
    // frequency modifications are listed as commands
    typedef struct {
        uint64_t core, uncore, thread;
    } freqPair;
    typedef struct {
        std::string key; // key value of this command, indicates the location (Loop, Function) of this modification command
        freqPair pre;  // frequency adjust before enter
        freqPair post; // frequency adjust after exit
    } FreqCommand_t;
    bool isInvalidFreqCommand(FreqCommand_t& c) { return c.pre.core==0 && c.pre.uncore==0 && c.pre.thread==0 && c.post.core==0 && c.post.uncore==0 && c.post.thread==0; }
    typedef std::unordered_map<std::string, FreqCommand_t> FreqCommandMap_t; 
    // This template is quite duplicated but I did not find better solution. 
    class ModelAdapter {
        public:
        ModelAdapter() { initialized=false; }
        void init(std::string fn) {
            if(initialized) return;
            initialized = true;
            if(isCached(fn)) {
                printf("\nINFO: read frequency commands from cached file\n");
                enableConcurrentCacheRead();
                readFreqCommandMapFromCache();
            } else {
                printf("\nWarning: Frequency command file could not open: %s", CACHE_FN.c_str());
                printf("\n         You should generate frequency commands from tools in PAETT-tool before compiling for frequency optimization.\n");
                initialized = false;
                return ;
            } // else isCached
            safe_close(cache);
        }
        FreqCommand_t getFreqCommand(std::string key) {
            if(!initialized) return {key, {0,0}, {0,0}};
            for(auto B=freqCommandMap.begin(),E=freqCommandMap.end();B!=E;++B) { 
                if(B->second.key==key) {
                    printf("%s Matched\n", key.c_str());
                    return B->second;
                }
            }
            return {key, {0,0}, {0,0}};
            // FreqCommandMap_t::iterator it = freqCommandMap.find(key);
            // if(it!=freqCommandMap.end()) {
            //     return it->second;
            // } else {
            //     return {key, {0,0}, {0,0}};
            // }
        }
        void printAllFreqCommand(FILE* fp=stdout) {
            fprintf(fp,"\n====== %lu commands constructed ======\n",freqCommandMap.size());
            for(auto B=freqCommandMap.begin(),E=freqCommandMap.end();B!=E;++B) {
                fprintf(fp,"%s:[key=%s]:pre=(%ld, %ld),post=(%ld, %ld)\n",B->first.c_str(),
                    B->second.key.c_str(),B->second.pre.core,B->second.pre.uncore, 
                    B->second.post.core, B->second.post.uncore);
            }
        }
        protected:
        bool initialized;
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
        std::string CACHE_FN; //="paett_model.cache";
        bool isCached(std::string fn) {
            CACHE_FN = fn;
            cache = safe_open(CACHE_FN.c_str(), "r");
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
        void readFreqCommandMapFromCache() {
            FreqCommand_t command;
            uint64_t key;
            int r0;
            char buff[200];
            while(EOF!=(r0=fscanf(cache, "%lx ", &key))) {
                // fscanf(cache, "%s", buff);
                r0=fscanf(cache, "%200[^;]", buff);
                command.key = std::string(buff);
                while(r0==200) {
                    r0=fscanf(cache, "%200[^;]", buff);
                    command.key += std::string(buff);
                }
                // fscanf(cache, "%lx",&command.key);
                fscanf(cache, ";%ld",&command.pre.core);
                fscanf(cache, "%ld",&command.pre.uncore);
                fscanf(cache, "%ld",&command.pre.thread);
                fscanf(cache, "%ld",&command.post.core);
                fscanf(cache, "%ld",&command.post.uncore);
                fscanf(cache, "%ld",&command.post.thread);
                // fprintf(stdout,"%lx %lx %ld %ld %ld %ld %ld %ld\n",key, command.key,
#ifdef DEBUG_PAETT
                fprintf(stdout,"%lx %s %ld %ld %ld %ld %ld %ld\n",key, command.key.c_str(),
                    command.pre.core,command.pre.uncore, command.pre.thread,
                    command.post.core, command.post.uncore, command.post.thread);
#endif
                freqCommandMap[command.key] = command;
            }
#ifdef DEBUG_PAETT
            printf("Read finish\n");
            printAllFreqCommand();
#endif
        }
        // void writeFreqCommandMapToCache() {
        //     fprintf(cache,"%d ",1); // placeholder to inform the cache file is valid
        //     for(auto B=freqCommandMap.begin(),E=freqCommandMap.end();B!=E;++B) {
        //         // fprintf(cache,"%lx:[key=%lx]:pre=(%ld, %ld),post=(%ld, %ld),thread=%ld\n",B->first,
        //         //     B->second.key,B->second.pre.core,B->second.pre.uncore, 
        //         //     B->second.post.core, B->second.post.uncore,
        //         //     B->second.thread);
        //         fprintf(cache,"%lx %lx %ld %ld %ld %ld %ld %ld\n",B->first, B->second.key,
        //             B->second.pre.core,B->second.pre.uncore, B->second.pre.thread,
        //             B->second.post.core, B->second.post.uncore, B->second.post.thread);
        //     }
        // }
        FreqCommandMap_t freqCommandMap;
    };
}