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

struct options_struct {
    string prof_fn;
    string keymap_fn;
    bool print_coverage;
    options_struct() : 
        prof_fn(PAETT_PERF_INSTPROF_FN".0"),
        keymap_fn(KEYMAP_FN".0"),
        print_coverage(false)
    {}
} options;

void readKeyMap(const char* fn) {
    uint64_t r;
    const size_t ONE = 1;
    const size_t BUFFSIZE = 500;
    FILE* fp = fopen(fn,"r");
    if(fp==NULL) {
        printf("Fetal Error: KeyMap File %s could not open!\n", fn);
        exit(-1);
    }
    CallingContextLog::readKeyString(fp, keyMap);
    fclose(fp);
}

void usage() {
    printf("Usage: filter_significant_profile <options>\n");
    printf("\tAvailable Options:\n");
    printf("\t\t--prof_fn <path/to/profile>\t:set path to PAETT's profile, the default value is %s\n", PAETT_PERF_INSTPROF_FN".0");
    printf("\t\t--prof_fn <path/to/profile>\t:set path to PAETT's keymap file, the default value is %s\n", KEYMAP_FN".0");
    printf("\t\t--print-coverage\t:calculate and print coverage of significant regions\n");
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
        } else if(opt==string("--keymap_fn")) {
            ++i;
            if(argc==i) {
                printf("--keymap_fn must have a value\n");
                usage();
                exit(1);
            }
            options.keymap_fn = string(argv[i]);
        } else if(opt==string("--print-coverage")) {
            options.print_coverage = true;
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
            if(keyMap[p->key]=="") {
                printf("\nError: empty key string detected for key value %ld!\n",p->key);
                while(p!=NULL) {
                    printf("%s=>",keyMap[p->key].c_str());
                    p = p->parent;
                }
                exit(1);
            }
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

double getTotalTime(CallingContextLog* root) {
    double time = 0;
    if(!root->pruned) {
        time += root->data.cycle;
    }
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        time += getTotalTime(CB->second);
    }
    return time;
}

double getSignificantTime(CallingContextLog* root, double total_time) {
    uint64_t time = 0;
    if(!root->pruned && root->data.cycle/root->data.ncall > PRUNE_THRESHOLD) {
        time += root->data.cycle;
        CallingContextLog* p = root;
        while(p!=NULL) {
            printf("%s=>",keyMap[p->key].c_str());
            p = p->parent;
        }
        printf(";%.2lf\n", (double)root->data.cycle/total_time*100);
    }
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        time += getSignificantTime(CB->second, total_time);
    }
    return time;
}

double getSignificantCoverage(CallingContextLog* root) {
    double tot = (double)getTotalTime(root);
    return (double)getSignificantTime(root, tot) / tot  * 100;
}

int main(int argc, char* argv[]) {
    parse_args(argc, argv);
    readKeyMap(options.keymap_fn.c_str());
    CallingContextLog* root = CallingContextLog::read(options.prof_fn.c_str());
    if(root==NULL) return 1;
    splitEnergyData(root);
    pruneCCTWithThreshold(root, PRUNE_THRESHOLD, false);
    if(options.print_coverage) {
        printf("Significant Coverage : %.2lf %%", getSignificantCoverage(root));
    } else {
        print_significant(root);
    }
    return 0;
}