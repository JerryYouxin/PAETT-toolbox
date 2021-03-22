#include "CallingContextTree.h"
struct FreqData : public DataBase {
    bool valid;
    double time;
    uint64_t ncall;
    uint64_t core;
    uint64_t uncore;
    uint64_t thread;
    void print(FILE* fp=stdout) { fprintf(fp, "[valid=%d] time=%lf (%ld calls), core=%ld, uncore=%ld, thread=%ld",valid,time,ncall,core,uncore,thread); }
};
template class CallingContextTree<FreqData>;
typedef CallingContextTree<FreqData> CCTRes;

CCTRes* __createCCTfromPreOrderList(CallingContextLog* root, std::vector<FreqData>& list, int *i) {
    // CCTRes* r = new CCTRes();
    CCTRes* r = CCTRes::get();
    assert(*i < list.size());
    r->key = root->key;
    r->data= list[*i];
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        *i = *i + 1;
        CCTRes* child = __createCCTfromPreOrderList(CB->second, list, i);
        assert(r->insertChild(child)!=NULL);
    }
    return r;
}

CCTRes* createCCTfromPreOrderList(CallingContextLog* root, std::vector<FreqData>& list) {
    int i = 0;
    return __createCCTfromPreOrderList(root, list, &i);
}