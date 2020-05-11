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
    string output;
    options_struct() : 
        prof_fn(PAETT_PERF_INSTPROF_FN".0"),
        output("paett.filt")
    {}
} options;

void usage() {
    printf("Usage: paett_read_profile <options>\n");
    printf("\tAvailable Options:\n");
    printf("\t\t--out <path/to/output>\t:set path to genereted PAETT's filter file for compiling, the default value is %s\n", "paett.filt");
    printf("\t\t--prof_fn <path/to/profile>\t:set path to PAETT's profile, the default value is %s\n", PAETT_PERF_INSTPROF_FN".0");
}

void parse_args(int argc, char* argv[]) {
    string opt;
    for(int i=1;i<argc;++i) {
        opt = string(argv[i]);
        if(opt==string("--out")) {
            ++i;
            if(argc==i) {
                printf("--prof_fn must have a value\n");
                usage();
                exit(1);
            }
            options.output = string(argv[i]);
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
    if(!root->pruned) {
        printf("%s+ %s",pre.c_str(), keyMap[root->key].c_str());
        if(print_data) {
            printf(":");
            root->data.print(stdout);
        }
        printf("\n");
    }
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        print_cct(CB->second, print_data, pre+"|  ");
    }
}

void __generate_filter(FILE* fp, CallingContextLog* root) {
    if(!root->pruned) {
        fprintf(fp, "%s\n", keyMap[root->key].c_str());
    }
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        __generate_filter(fp, CB->second);
    }
}

void generate_filter(CallingContextLog* root, const char* fn) {
    FILE* fp = fopen(fn, "w");
    if(fp==NULL) {
        printf("Failed to open output file %s\n", fn);
        exit(1);
    }
    __generate_filter(fp, root);
    fclose(fp);
}

int main(int argc, char* argv[]) {
    parse_args(argc, argv);
    readKeyMap();
    CallingContextLog* root = CallingContextLog::read(options.prof_fn.c_str());
    pruneCCTWithThreshold(root, PRUNE_THRESHOLD, false);
    print_cct(root, false);
    generate_filter(root, options.output.c_str());
    return 0;
}