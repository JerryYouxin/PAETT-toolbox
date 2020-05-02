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
    FILE* fp = fopen(KEYMAP_FN,"r");
    if(fp==NULL) {
        printf("Fetal Error: KeyMap File %s could not open!\n", KEYMAP_FN);
        exit(-1);
    }
    CallingContextLog::readKeyString(fp, keyMap);
    fclose(fp);
}

struct options_struct {
    string prof_fn;
    bool print_data;
    bool print_significant;
    options_struct() : 
        prof_fn(PAETT_PERF_INSTPROF_FN".0"),
        print_data(true),
        print_significant(true)
    {}
} options;

void usage() {
    printf("Usage: paett_read_profile <options>\n");
    printf("\tAvailable Options:\n");
    printf("\t\t--print-data\t:print CallingContextTree with profiled data\n");
    printf("\t\t--print-significant\t:print automatically detected significant regions\n");
    printf("\t\t--prof_fn <path/to/profile>\t:set path to PAETT's profile, the default value is %s\n", PAETT_PERF_INSTPROF_FN".0");
}

void parse_args(int argc, char* argv[]) {
    string opt;
    for(int i=1;i<argc;++i) {
        opt = string(argv[i]);
        if(opt==string("--print-data")) {
            options.print_data = true;
        } else if(opt==string("--print-significant")) {
            options.print_significant = true;
        } else if(opt==string("--prof_fn")) {
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

void print_cct(CallingContextLog* root, bool print_data, string pre="") {
    printf("%s+ %s",pre.c_str(), keyMap[root->key].c_str());
    if(root->pruned) {
        printf(" (pruned)");
    }
    if(print_data) {
        printf(":");
        root->data.print(stdout);
    }
    printf("\n");
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        print_cct(CB->second, print_data, pre+"|  ");
    }
}

void print_significant(CallingContextLog* root) {
    if(!root->pruned && root->data.cycle/root->data.ncall > PRUNE_THRESHOLD) {
        printf("\t%s: ", keyMap[root->key].c_str());
        printf("%ld us (%ld calls)\n", root->data.cycle, root->data.ncall);
    }
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        print_significant(CB->second);
    }
}

int main(int argc, char* argv[]) {
    parse_args(argc, argv);
    readKeyMap();
    CallingContextLog* root = CallingContextLog::read(options.prof_fn.c_str());
    printf("Calling Context Tree:\n\n");
    print_cct(root, options.print_data);
    if(options.print_significant) {
        printf("Pruning Threshold = %ld us\n", PRUNE_THRESHOLD);
        pruneCCTWithThreshold(root, PRUNE_THRESHOLD);
        printf("\nSignificant Regions:\n");
        print_significant(root);
    }
    return 0;
}