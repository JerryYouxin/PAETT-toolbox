#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string>
#include <unordered_map>
#include "common.h"
#include "config.h"
#include "CallingContextTree.h"

using namespace std;
unordered_map<uint64_t, string> keyMap;

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

struct options_struct {
    string prof_fn;
    options_struct() : 
        prof_fn(PAETT_PERF_INSTPROF_FN".0")
    {}
} options;

void usage() {
    printf("Usage: filter_significant_profile <options>\n");
    printf("\tAvailable Options:\n");
    printf("\t\t--prof_fn <path/to/profile>\t:set path to PAETT's profile, the default value is %s\n", PAETT_PERF_INSTPROF_FN".0");
}

void parse_args(int argc, char* argv[]) {
    string opt;
    for(int i=1;i<argc;++i) {
        opt = string(argv[i]);
        if(opt==string("--prof_fn")) {
            ++i;
            if(argc==i) {
                printf("--prof_fn must have a value\n");
                usage();
                exit(1);
            }
            options.prof_fn = string(argv[i]);
        } else {
            goto unknown;
        }
    }
    return ;
unknown:
    printf("Unknown argument %s\n", opt.c_str());
    usage();
    exit(1);
}

void print_significant(CallingContextLog* root) {
    if(!root->pruned && root->data.cycle/root->data.ncall > PRUNE_THRESHOLD) {
        CallingContextLog* p = root;
        while(p!=NULL) {
            printf("%s=>",keyMap[p->key].c_str());
            p = p->parent;
        }
        printf(";");
        for(int i=0;i<root->data.size;++i) {
            printf("%ld ", root->data.eventData[i]);
        }
        printf("%lf\n", root->data.pkg_energy);
    }
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        print_significant(CB->second);
    }
}

void mergeEventData(CallingContextLog* root) {
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        mergeEventData(CB->second);
        for(int i=0;i<root->data.size;++i) {
            root->data.eventData[i] += CB->second->data.eventData[i];
        }
    }
}

void splitEnergyData(CallingContextLog* root) {
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        root->data.pkg_energy -= CB->second->data.pkg_energy;
        splitEnergyData(CB->second);
    }
}

int main(int argc, char* argv[]) {
    parse_args(argc, argv);
    readKeyMap();
    CallingContextLog* root = CallingContextLog::read(options.prof_fn.c_str());
    if(root==NULL) return 1;
    splitEnergyData(root);
    pruneCCTWithThreshold(root, PRUNE_THRESHOLD, false);
    print_significant(root);
    return 0;
}