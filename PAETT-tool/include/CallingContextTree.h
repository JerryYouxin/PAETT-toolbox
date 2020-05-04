#pragma once

#include <unordered_map>
#include <vector>
#include <string>
#include <sstream>
#include <cassert>
#include <cstring>

#include <iostream>

#include "common.h"
// actually, this indicates main function (entry function of a program)
#define CCT_ROOT_KEY -1
#define CCT_INVALID_KEY ((uint64_t)-2)
// Data_t must have fprint/fread method
template<typename Data_t>
struct CallingContextTree {
#ifdef PREALLOCATE_CCT
    typedef std::vector<std::pair<uint64_t, CallingContextTree<Data_t>*> > ChildList;
#else
    typedef std::unordered_map<uint64_t, CallingContextTree<Data_t>*> ChildList;
#endif
    uint64_t key;
    Data_t data;
    CallingContextTree<Data_t>* parent;
    ChildList children;
    bool pruned;
#ifdef PREALLOCATE_CCT
    #define CCT_PREALLOCATE_SIZE (1L<<20)
    static CallingContextTree<Data_t>* get() {
        static int psize = 0;
        static CallingContextTree<Data_t> pnodes[CCT_PREALLOCATE_SIZE];
        assert(psize<CCT_PREALLOCATE_SIZE && "CCT Number exceeds the preallocated size!");
        return &pnodes[psize++];
    }
    static void free(CallingContextTree<Data_t>*) {}
#else
    static CallingContextTree<Data_t>* get() {
        return new CallingContextTree<Data_t>();
    }
    static void free(CallingContextTree<Data_t>* p) {
        delete p;
    }
#endif
    void printStack() {
        printf("  [0x%lx]:",key);
        data.print();
        printf("\n");
        if(parent!=NULL) {
            parent->printStack();
        }
    }
    uint64_t length() {
        if(!parent) return 1;
        return parent->length()+1;
    }
    CallingContextTree<Data_t>* findStack(uint64_t key) {
        if(key==this->key) {
            return this;
        }
        if(parent) {
            return parent->findStack(key);
        }
        return NULL;
    }
#ifdef PREALLOCATE_CCT
    void addChild(CallingContextTree<Data_t>* c) {
        children.push_back(std::make_pair(c->key, c)); c->parent = this;
    }
#else
    void addChild(CallingContextTree<Data_t>* c) {
        children[c->key] = c; c->parent = this;
    }
#endif
    CallingContextTree<Data_t>* getOrInsertChild(uint64_t key, bool default_pruned=false) {
#ifdef PREALLOCATE_CCT
        auto ic=children.end();
        assert(children.size()>=0);
        if(children.size()>0) {
            ic = children.begin();
            while(ic!=children.end() && ic->first!=key) ++ic;
        }
#else
        auto ic = children.find(key);
#endif
        if(ic!=children.end()) return ic->second;
        // This is a new key. Insert a new children
        CallingContextTree<Data_t>* c = CallingContextTree<Data_t>::get();// new CallingContextTree<Data_t>();
        c->key=key; c->pruned = default_pruned;
        addChild(c);
        return c;
    }
    CallingContextTree<Data_t>* insertChild(CallingContextTree<Data_t>* child) {
        uint64_t key = child->key;
#ifdef PREALLOCATE_CCT
        auto ic = children.begin();
        while(ic!=children.end() && ic->first!=key) ++ic;
#else
        auto ic = children.find(key);
#endif
        if(ic!=children.end()) return NULL;
        // This is a new key. Insert a new children
        CallingContextTree<Data_t>* c = child;
        c->key=key;
        addChild(c);
        return c;
    }
    void clear() {
        parent=NULL; key=CCT_INVALID_KEY;
        for(auto CB=children.begin(), CE=children.end();CB!=CE;++CB) {
            CB->second->clear();
            CallingContextTree<Data_t>::free(CB->second);
        }
        children.clear();
    }
    void getPreOrderList(std::vector<Data_t>& res) {
        res.push_back(data);
        for(auto CB=children.begin(), CE=children.end();CB!=CE;++CB) {
            CB->second->getPostOrderList(res);
        }
    }
    void getPostOrderList(std::vector<Data_t>& res) {
        for(auto CB=children.begin(), CE=children.end();CB!=CE;++CB) {
            CB->second->getPostOrderList(res);
        }
        res.push_back(data);
    }
    // in backtrace order
    void getPathToRoot(std::vector<CallingContextTree<Data_t>*>& path) {
        CallingContextTree<Data_t>* root = this;
        while(!root && !(root->parent) && root->key!=CCT_ROOT_KEY) { path.push_back(root); root = root->parent; }
    }
    // return the leaf of the copied path
    CallingContextTree<Data_t>* copyCCTPath(CallingContextTree<Data_t>* src) {
        assert(src!=NULL);
        // find path to root first
        std::vector<CallingContextTree<Data_t>*> path;
        src->getPathToRoot(path);
        // now copy CCT Path from src's root. Data will not be copied
        CallingContextTree<Data_t>* cur = this;
        // note that path is in backtrace order, so iterate with reverse order
        for(auto B=path.rbegin(), E=path.rend(); B!=E; ++B) {
            cur = cur->getOrInsertChild((*B)->key);
        }
        return cur;
    }
    static void fprint(const char* fn, CallingContextTree<Data_t>* root) {
        FILE* fp = fopen(fn, "wb");
        fprint(fp, root);
        fclose(fp);
    }
    static CallingContextTree<Data_t>* read(FILE* fp, uint64_t key=CCT_ROOT_KEY) {
        const uint64_t ONE = 1; int r;
        CallingContextTree<Data_t>* root=CallingContextTree<Data_t>::get();//new CallingContextTree<Data_t>();
        root->key = key;
        // read data through fread interface
        SAFE_READ(&(root->pruned), sizeof(bool), ONE, fp);
        root->data.read(fp);
        // read from binary file
        uint64_t size,val, i;
        SAFE_READ(&size, sizeof(uint64_t), ONE, fp);
        for(i=0;i<size;++i) {
            SAFE_READ(&val, sizeof(uint64_t), ONE, fp);
            root->addChild(read(fp, val));
        }
        return root;
    }
    static CallingContextTree<Data_t>* read(const char* fn) {
        FILE* fp = fopen(fn, "rb");
        CallingContextTree<Data_t>* root = read(fp);
        fclose(fp);
        return root;
    }
    static void print(CallingContextTree<Data_t>* root, FILE* fp=stdout, std::string pre="") {
        fprintf(fp,"%s0x%lx:",pre.c_str(),root->key);
        root->data.print(fp);
        fprintf(fp,"\n");
        for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
            print(CB->second, fp, pre+"=>");
        }
    }
    ~CallingContextTree() { clear(); }
#ifdef PREALLOCATE_CCT
    CallingContextTree() { pruned=false; parent=NULL; key=CCT_ROOT_KEY; data.clear(); children.reserve(16); }
#else
    CallingContextTree() { pruned=false; parent=NULL; key=CCT_ROOT_KEY; data.clear(); }
#endif
    static void fprint(FILE* fp, CallingContextTree<Data_t>* root) {
        const uint64_t ONE = 1;
        int r;
        // write data through fprint interface
        SAFE_WRITE(&(root->pruned), sizeof(bool), ONE, fp);
        root->data.fprint(fp);
        // binary file
        uint64_t val = root->children.size();
        SAFE_WRITE(&val, sizeof(uint64_t), ONE, fp);
        for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
            val = CB->first;
            SAFE_WRITE(&val, sizeof(uint64_t), ONE, fp);
            fprint(fp, CB->second);
        }
    }
    static void fprintKeyString(FILE* fp, CallingContextTree<Data_t>* root) {
        fprintf(fp, "%ld %s\n", root->key, (root->key==CCT_ROOT_KEY)?"ROOT":(root->key==CCT_INVALID_KEY?"INVALID":reinterpret_cast<char*>(root->key)));
        for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
            fprintKeyString(fp, CB->second);
        }
    }
    static void readKeyString(FILE* fp, std::unordered_map<uint64_t, std::string>& keyMap) {
        uint64_t keyVal;
        char buff[200];
        while(EOF!=fscanf(fp, "%ld ",&keyVal)) {
            fscanf(fp, "%[^\n]\n", buff);
            keyMap[keyVal] = std::string(buff);
        }
    }
};

template <typename T1, typename T2>
class TransformerBase {
    public:
    virtual void handler(uint64_t, T1&, T2&, bool) = 0;
};

template <typename T1, typename T2>
static void transferCCTwith(CallingContextTree<T1>* src, CallingContextTree<T2>* dst, TransformerBase<T1,T2>* transformer) {
    dst->key = src->key;
    dst->pruned = src->pruned;
    for(auto CB=src->children.begin(), CE=src->children.end();CB!=CE;++CB) {
        transferCCTwith(CB->second,dst->getOrInsertChild(CB->first),transformer);
        int i;
        for(i=0;i<src->data.size;++i) {
            src->data.eventData[i] += CB->second->data.eventData[i];
        }
    }
#ifdef DEBUG
    printf("[%lx]:",src->key);
    src->data.print();
    printf(":");
#endif
    transformer->handler(src->key, src->data, dst->data, !(dst->pruned));
#ifdef DEBUG
    printf("==>[%lx]:",dst->key);
    dst->data.print();
    printf("\n");
#endif
}

template <typename T1, typename T2>
static CallingContextTree<T2>* createCCTfrom(CallingContextTree<T1>* src, TransformerBase<T1,T2>* transformer) {
    CallingContextTree<T2>* dst = CallingContextTree<T2>::get();// new CallingContextTree<T2>();
    transferCCTwith<T1,T2>(src, dst, transformer);
    return dst;
}

struct DataBase {
    DataBase() {}
    ~DataBase() {}
    virtual void fprint(FILE* fp) {}
    virtual void read(FILE* fp) {}
    virtual void print(FILE* fp=stdout) {}
    virtual void clear() {}
};

struct DataLog {
    uint64_t ncall; // number of entering this calling context
    uint64_t cycle; // number of sampled cycle of this datalog
    uint64_t active_thread;
    double pkg_energy;
    double last_energy;
    uint64_t size;
    uint64_t* eventData;
    DataLog();
    void fprint(FILE* fp);
    void read(FILE* fp);
    void print(FILE* fp=stdout);
    void clear();
};

template class CallingContextTree<DataLog>;
typedef CallingContextTree<DataLog> CallingContextLog;

static void __printDistribution(CallingContextLog* root, uint64_t tot_cyc, double T, std::string pre="") {
    printf("%s0x%lx:",pre.c_str(),root->key);
    root->data.print();
    double rate = (double)root->data.cycle/(double)tot_cyc;
    printf(":%lfus(%lf%%):(%ld/%ld)\n",T*rate, rate*100,root->data.cycle,tot_cyc);
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        __printDistribution(CB->second, tot_cyc, T, pre+"=>");
    }
}

static uint64_t __countTotCyc(CallingContextLog* root) {
    uint64_t tot_cyc = root->data.cycle;
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        tot_cyc += __countTotCyc(CB->second);
    }
    return tot_cyc;
}

static void printDistribution(CallingContextLog* root, double T=0.0) {
    uint64_t tot_cyc = __countTotCyc(root);
    __printDistribution(root, tot_cyc, T);
}

static void __printMetrics(FILE* fp, CallingContextLog* root) {
    bool print=false;
    int i;
    // for(i=0;i<root->data.size;++i) { 
    //     if(root->data.eventData[i]!=0) {
    //         print=true;
    //         break;
    //     }
    // }
    // if(print) {
        fprintf(fp, "%lu %lu", root->key, root->data.cycle);
        for(i=0;i<root->data.size;++i) {
            fprintf(fp, " %ld", root->data.eventData[i]);
        }
        fprintf(fp, "\n");
    // }
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        __printMetrics(fp, CB->second);
    }
}

static void printMetrics(FILE* fp, CallingContextLog* root) {
    // uint64_t tot_cyc = __countTotCyc(root);
    __printMetrics(fp, root);
}

static void mergeMetrics(CallingContextLog* root, std::unordered_map<uint64_t, DataLog>& MM) {
    std::unordered_map<uint64_t, DataLog>::iterator it;
    it = MM.find(root->key);
    if(it==MM.end()) {
        DataLog dlog = root->data;
        if(dlog.size!=0) {
            assert(dlog.eventData!=NULL);
            dlog.eventData = (uint64_t*)malloc(sizeof(uint64_t)*dlog.size);
            memcpy(dlog.eventData, root->data.eventData, sizeof(uint64_t)*dlog.size);
        }
        MM[root->key] = dlog;
    } else {
        uint64_t i,size = it->second.size;
        assert(size==root->data.size);
        for(i=0;i<size;++i) {
            it->second.eventData[i] += root->data.eventData[i];
        }
        it->second.pkg_energy += root->data.pkg_energy;
        it->second.cycle += root->data.cycle;
        it->second.ncall += root->data.ncall;
    }
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        mergeMetrics(CB->second, MM);
    }
}

static void printMergedMetrics(FILE* fp, CallingContextLog* root) {
    int i;
    std::unordered_map<uint64_t, DataLog> MM;
    mergeMetrics(root, MM);
    for(std::unordered_map<uint64_t, DataLog>::iterator B=MM.begin(), E=MM.end(); B!=E; ++B) {
        fprintf(fp, "%lu %lu", B->first, B->second.cycle);
        for(i=0;i<B->second.size;++i) {
            fprintf(fp, " %ld", B->second.eventData[i]);
        }
        fprintf(fp, "\n");
    }
}

static std::string updateMergedMetrics(FILE* fp, CallingContextLog* root) {
    int i;
    uint64_t key, cycle;
    char c;
    std::stringstream s;
    std::unordered_map<uint64_t, DataLog> MM;
    mergeMetrics(root, MM);
    for(std::unordered_map<uint64_t, DataLog>::iterator B=MM.begin(), E=MM.end(); B!=E; ++B) {
        fscanf(fp, "%lu %lu", &key, &cycle);
        std::string buff = "";
        fscanf(fp, "%c",&c);
        while(c!='\n') {
            buff += c;
            fscanf(fp, "%c",&c);
        }
        s << key << " " << cycle << buff;
        for(int i=0;i<B->second.size;++i) {
            s << " " << B->second.eventData[i];
        }
        s << "\n";
    }
    return s.str();
}

static std::string updateMetrics(FILE* fp, CallingContextLog* root) {
    uint64_t key, cycle;
    std::string buff = "";
    char c;
    fscanf(fp, "%lu %lu", &key, &cycle);
    assert(key == root->key);
    fscanf(fp, "%c",&c);
    while(c!='\n') {
        buff += c;
        fscanf(fp, "%c",&c);
    }
    std::stringstream s;
    s << key << " " << cycle << buff;
    for(int i=0;i<root->data.size;++i) {
        s << " " << root->data.eventData[i];
    }
    s << "\n";
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        s << updateMetrics(fp, CB->second);
    }
    return s.str();
}

static void updateCCTMetrics(FILE* fp, CallingContextLog* root) {
    uint64_t key, cycle;
    std::string buff = "";
    char c;
    fscanf(fp, "%lu %lu", &key, &cycle);
    assert(key == root->key);
    fscanf(fp, "%c",&c);
    while(c!='\n') {
        buff += c;
        fscanf(fp, "%c",&c);
    }
    uint64_t m;
    std::vector<uint64_t> ml;
    std::stringstream s(buff);
    while ( s >> m ) {
        ml.push_back(m);
    }
    // update data
    for(int i=0;i<root->data.size;++i) {
        ml.push_back(root->data.eventData[i]);
    }
    root->data.size = ml.size();
    // free(root->data.eventData);
    root->data.eventData = (uint64_t*)malloc(sizeof(uint64_t)*root->data.size);
    for(int i=0;i<root->data.size;++i) {
        root->data.eventData[i] = ml[i];
    }
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        updateCCTMetrics(fp, CB->second);
    }
}

static void printMergedEnergy(FILE* fp, CallingContextLog* root) {
    int i;
    std::unordered_map<uint64_t, DataLog> MM;
    mergeMetrics(root, MM);
    for(std::unordered_map<uint64_t, DataLog>::iterator B=MM.begin(), E=MM.end(); B!=E; ++B) {
        fprintf(fp, "%lu %lu %.6lf\n", B->first, B->second.cycle, B->second.pkg_energy);
    }
}

bool pruneCCTWithThreshold(CallingContextLog* cur, double threshold);