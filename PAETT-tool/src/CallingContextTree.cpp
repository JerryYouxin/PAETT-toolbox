#include "CallingContextTree.h"
#define max(a, b) ((a)>(b)?(a):(b))

void DataLog::fprint(FILE* fp) {
    uint64_t r;
    const uint64_t ONE=1;
    SAFE_WRITE(&ncall, sizeof(uint64_t), ONE, fp);
    SAFE_WRITE(&cycle, sizeof(uint64_t), ONE, fp);
    SAFE_WRITE(&pkg_energy, sizeof(double), ONE, fp);
    SAFE_WRITE(&active_thread, sizeof(uint64_t), ONE, fp);
    SAFE_WRITE(&size, sizeof(uint64_t), ONE, fp);
    if(size!=0)
        SAFE_WRITE(eventData, sizeof(uint64_t), size, fp);
}

void DataLog::print(FILE* fp) {
    fprintf(fp,"%ld %ld (%.2lf, %.2lf) active thread=%ld, size=%ld:[",ncall,cycle, pkg_energy, last_energy, active_thread, size);
    if(size!=0) {
        fprintf(fp,"%ld",eventData[0]);
        for(uint64_t i=1;i<size;++i) {
            fprintf(fp,",%ld",eventData[i]);
        }
        fprintf(fp,"]");
    } else {
        fprintf(fp,"null]");
    }
}

void DataLog::read(FILE* fp) {
    uint64_t r;
    const uint64_t ONE=1;
    SAFE_READ(&ncall, sizeof(uint64_t), ONE, fp);
    SAFE_READ(&cycle, sizeof(uint64_t), ONE, fp);
    SAFE_READ(&pkg_energy, sizeof(double), ONE, fp);
    SAFE_READ(&active_thread, sizeof(uint64_t), ONE, fp);
    SAFE_READ(&size, sizeof(uint64_t), ONE, fp);
    if(size!=0) {
        eventData = (uint64_t*)malloc(sizeof(uint64_t)*size);
        SAFE_READ(eventData, sizeof(uint64_t), size, fp);
    }
}

DataLog::DataLog() {
    ncall=0; cycle=0; size=0; eventData=NULL; pkg_energy=0; active_thread=0;
}

void DataLog::clear() {
    ncall=0; cycle=0; size=0;
    // if(eventData!=0) free(eventData);
    // eventData=0;
}

void __mergePrunedNode(CallingContextLog* cur) {
    for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
        // make sure the children has already merged for pruned node
        __mergePrunedNode(CB->second);
        // if this child is pruned, merge data to his parent (cur)
        if(CB->second->pruned) {
            cur->data.cycle += CB->second->data.cycle;
            for(int i=0;i<cur->data.size;++i) {
                cur->data.eventData[i] += CB->second->data.eventData[i];
            }
            cur->data.active_thread = max(cur->data.active_thread, CB->second->data.active_thread);
        }
    }
}

#ifdef USE_OLD_PRUNE
static std::unordered_map<uint64_t, uint64_t> prunedRegion;
bool __pruneAllPrunedRegions(CallingContextLog* cur, bool erase_pruned) {
    bool prune = true;
    std::vector<CallingContextLog::ChildList::iterator> prunedChildren;
    for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
        bool childPrune = __pruneAllPrunedRegions(CB->second, erase_pruned);
        if(erase_pruned && childPrune) {
            prunedChildren.push_back(CB);
        }
        prune &= childPrune;
    }
    if(erase_pruned) {
        // actual prune work of the pruned subtree
        for(auto CB=prunedChildren.begin(), CE=prunedChildren.end();CB!=CE;++CB) {
            CallingContextLog::ChildList::iterator key = *CB;
            cur->data.cycle += key->second->data.cycle;
            cur->data.active_thread = max(cur->data.active_thread, key->second->data.active_thread);
            for(int i=0;i<cur->data.size;++i) {
                cur->data.eventData[i] += key->second->data.eventData[i];
            }
            cur->children.erase(key);
        }
    }
    cur->pruned = cur->pruned || (prunedRegion.find(cur->key)!=prunedRegion.end());
    return prune && cur->pruned;
}

bool __pruneCCTWithThreshold(CallingContextLog* cur, double threshold, bool erase_pruned) {
    bool prune = true;
    std::vector<CallingContextLog::ChildList::iterator> prunedChildren;
    // try to prune its children first to get more accurate time estimation for this node
    for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
        bool childPrune = __pruneCCTWithThreshold(CB->second, threshold, erase_pruned);
        if(erase_pruned && childPrune) {
            prunedChildren.push_back(CB);
        }
        prune &= childPrune;
    }
    // actual prune work of the pruned subtree
    if(erase_pruned) {
        for(auto CB=prunedChildren.begin(), CE=prunedChildren.end();CB!=CE;++CB) {
            CallingContextLog::ChildList::iterator key = *CB;
            cur->data.cycle += key->second->data.cycle;
            for(int i=0;i<cur->data.size;++i) {
                cur->data.eventData[i] += key->second->data.eventData[i];
            }
            cur->data.active_thread = max(cur->data.active_thread, key->second->data.active_thread);
            cur->children.erase(key);
        }
    }
    // if all chldren are pruned, this node may be pruned, so check it
    if(prune) {
        // get actual time assumed to be executed exactly in this function (exclude his *valid* children's)
        double time = cur->data.cycle;
        // for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
        //     time += CB->second->data.cycle;
        // }
        // now update the time
        time /= cur->data.ncall; // per call time
        // simple and aggresive pruning methodology
        prune = (cur->pruned||(time < threshold));
        cur->pruned = prune;
    }
    if(prune) {
        prunedRegion[cur->key] = 0;
    }
    return prune;
}

bool pruneCCTWithThreshold(CallingContextLog* cur, double threshold, bool erase_pruned) {
    bool pruned = __pruneCCTWithThreshold(cur, threshold, erase_pruned);
    pruned = pruned && __pruneAllPrunedRegions(cur, erase_pruned);
    if(!erase_pruned) {
        __mergePrunedNode(cur);
    }
    return pruned;
}
#else
struct filterMetrics {
    uint64_t cycle;
    uint64_t ncall;
};

void __mergeAllRegionsFromCCT(CallingContextLog* cur, std::unordered_map<uint64_t, filterMetrics> &regionMetrics) {
    auto it = regionMetrics.find(cur->key);
    filterMetrics fm;
    fm.cycle = 0;
    fm.ncall = 0;
    CallingContextLog* p = cur->__getFirstNode();
    while(p!=p->next) {
        fm.cycle += p->data.cycle;
        fm.ncall += p->data.ncall;
        p = p->next;
    }
    fm.cycle += p->data.cycle;
    fm.ncall += p->data.ncall;
    if(it==regionMetrics.end()) {
        regionMetrics[cur->key] = fm;
    } else {
        regionMetrics[cur->key].cycle += fm.cycle;
        regionMetrics[cur->key].ncall += fm.ncall;
    }
    for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
        __mergeAllRegionsFromCCT(CB->second, regionMetrics);
    }
}

bool __pruneCCTWithThreshold(CallingContextLog* cur, double threshold, bool erase_pruned, std::unordered_map<uint64_t, filterMetrics>& regionMetrics) {
    auto it = regionMetrics.find(cur->key);
    // if the merged metric is lower than threshold, this node may be pruned
    bool prune = (it==regionMetrics.end() || ((double)it->second.cycle/(double)it->second.ncall)<threshold);
    std::vector<CallingContextLog::ChildList::iterator> prunedChildren;
    // if all chldren are pruned, this node may be pruned
    for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
        bool childPrune = __pruneCCTWithThreshold(CB->second, threshold, erase_pruned, regionMetrics);
        if(childPrune && erase_pruned) {
            prunedChildren.push_back(CB);
        }
        prune &= childPrune;
    }
    // actual prune work of the pruned subtree
    if(erase_pruned) {
        for(auto CB=prunedChildren.begin(), CE=prunedChildren.end();CB!=CE;++CB) {
            CallingContextLog::ChildList::iterator key = *CB;
            CallingContextLog* p = key->second->__getFirstNode();
            while(p!=p->next) {
                cur->data.cycle += p->data.cycle;
                for(int i=0;i<cur->data.size;++i) {
                    cur->data.eventData[i] += p->data.eventData[i];
                }
                cur->data.active_thread = max(cur->data.active_thread, p->data.active_thread);
            }
            cur->data.cycle += p->data.cycle;
            for(int i=0;i<cur->data.size;++i) {
                cur->data.eventData[i] += p->data.eventData[i];
            }
            cur->data.active_thread = max(cur->data.active_thread, p->data.active_thread);
            cur->children.erase(key);
        }
    }
    cur->pruned = cur->pruned || prune;
    return prune;
}

bool pruneCCTWithThreshold(CallingContextLog* cur, double threshold, bool erase_pruned) {
    std::unordered_map<uint64_t, filterMetrics> regionMetrics;
    __mergeAllRegionsFromCCT(cur, regionMetrics);
    bool pruned = __pruneCCTWithThreshold(cur, threshold, erase_pruned, regionMetrics);
    if(!erase_pruned) {
        __mergePrunedNode(cur);
    }
    return pruned;
}
#endif