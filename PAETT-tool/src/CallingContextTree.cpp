#include "CallingContextTree.h"

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

static std::unordered_map<uint64_t, uint64_t> prunedRegion;

bool __pruneAllPrunedRegions(CallingContextLog* cur) {
    bool prune = true;
    std::vector<CallingContextLog::ChildList::iterator> prunedChildren;
    for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
        bool childPrune = __pruneAllPrunedRegions(CB->second);
        if(childPrune) {
            prunedChildren.push_back(CB);
        }
        prune &= childPrune;
    }
    // actual prune work of the pruned subtree
    for(auto CB=prunedChildren.begin(), CE=prunedChildren.end();CB!=CE;++CB) {
        CallingContextLog::ChildList::iterator key = *CB;
        cur->data.cycle += key->second->data.cycle;
        for(int i=0;i<cur->data.size;++i) {
            cur->data.eventData[i] += key->second->data.eventData[i];
        }
        cur->children.erase(key);
    }
    cur->pruned = cur->pruned || (prunedRegion.find(cur->key)!=prunedRegion.end());
    return prune && cur->pruned;
}

bool __pruneCCTWithThreshold(CallingContextLog* cur, double threshold) {
    bool prune = true;
    std::vector<CallingContextLog::ChildList::iterator> prunedChildren;
    // try to prune its children first to get more accurate time estimation for this node
    for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
        bool childPrune = __pruneCCTWithThreshold(CB->second, threshold);
        if(childPrune) {
            prunedChildren.push_back(CB);
        }
        prune &= childPrune;
    }
    // actual prune work of the pruned subtree
    for(auto CB=prunedChildren.begin(), CE=prunedChildren.end();CB!=CE;++CB) {
        CallingContextLog::ChildList::iterator key = *CB;
        cur->data.cycle += key->second->data.cycle;
        for(int i=0;i<cur->data.size;++i) {
            cur->data.eventData[i] += key->second->data.eventData[i];
        }
        cur->children.erase(key);
    }
    // if all chldren are pruned, this node may be pruned, so check it
    if(prune) {
        // get actual time assumed to be executed exactly in this function (exclude his *valid* children's)
        double time = cur->data.cycle;
        for(auto CB=cur->children.begin(), CE=cur->children.end();CB!=CE;++CB) {
            time += CB->second->data.cycle;
        }
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

bool pruneCCTWithThreshold(CallingContextLog* cur, double threshold) {
    bool pruned = __pruneCCTWithThreshold(cur, threshold);
    pruned = pruned && __pruneAllPrunedRegions(cur);
    return pruned;
}