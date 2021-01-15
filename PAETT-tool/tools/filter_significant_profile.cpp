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

int warn_count = 0;

struct options_struct {
    string prof_fn;
    string keymap_fn;
    bool print_coverage;
    bool werror;
    bool nowarn;
    options_struct() : 
        prof_fn(PAETT_PERF_INSTPROF_FN".0"),
        keymap_fn(KEYMAP_FN".0"),
        print_coverage(false),
        werror(false),
        nowarn(false)
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
    printf("\t\t--Werror\t:set to stop and report for error when warning is detected\n");
    printf("\t\t--no-warn\t:set to skip all warning\n");
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
        } else if(opt==string("--Werror")) {
            options.werror = true;
        } else if(opt==string("--no-warn")) {
            options.nowarn = true;
        }else {
            goto unknown;
        }
    }
    return ;
unknown:
    printf("Unknown argument %s\n", opt.c_str());
    usage();
    exit(1);
}

// void print_significant(CallingContextLog* root) {
//     if(!root->pruned && root->data.cycle/root->data.ncall > PRUNE_THRESHOLD) {
//         CallingContextLog* p = root;
//         while(p!=NULL) {
//             if(keyMap[p->key]=="") {
//                 printf("\nError: empty key string detected for key value %ld!\n",p->key);
//                 while(p!=NULL) {
//                     printf("%s=>",keyMap[p->key].c_str());
//                     p = p->parent;
//                 }
//                 exit(1);
//             }
//             printf("%s=>",keyMap[p->key].c_str());
//             p = p->parent;
//         }
//         printf(";");
//         for(int i=0;i<root->data.size;++i) {
//             printf("%ld ", root->data.eventData[i]);
//         }
//         printf("%lf\n", root->data.pkg_energy);
//     }
//     for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
//         print_significant(CB->second);
//     }
// }
void print_significant(CallingContextLog* root, std::string pre);
void __print_node(CallingContextLog* p, std::string pre) {
    printf("%sEnter;%s;%ld;%ld;%ld;",pre.c_str(),keyMap[p->key].c_str(),p->start_index,p->end_index,p->data.active_thread);
    for(int i=0;i<p->data.size;++i) {
        printf("%ld ", p->data.eventData[i]);
    }
    printf("%lf\n", p->data.pkg_energy);
    for(auto CB=p->children.begin(), CE=p->children.end();CB!=CE;++CB) {
        print_significant(CB->second, pre+"  ");
    }
    printf("%sExit\n",pre.c_str());
}
// print .dat format file to stdout
void print_significant(CallingContextLog* root, std::string pre="") {
    if(!root->pruned) {
        CallingContextLog* p = root->__getFirstNode();
        if(keyMap[p->key]=="") {
            warn_count++;
            if(options.werror) {
                fprintf(stderr, "Error: empty key string detected for key value %ld!\n",p->key);
                while(p!=NULL) {
                    printf("%s=>",keyMap[p->key].c_str());
                    p = p->parent;
                }
                printf("\n");
                exit(1);
            }
            if(!options.nowarn) {
                fprintf(stderr, "\nWarning: empty key string detected for key value %ld. Ignore this CCT\n",p->key);
                fprintf(stderr, "         ");
                while(p!=NULL) {
                    fprintf(stderr,"%s=>",keyMap[p->key].c_str());
                    p = p->parent;
                }
                fprintf(stderr, "\n");
            }
            return;
        }
        while(p!=p->next) {
            __print_node(p, pre);
            p = p->next;
        }
        __print_node(p, pre);
    } else {
        for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
            print_significant(CB->second, pre+"  ");
        }
    }
}

void mergeEventData(CallingContextLog* root) {
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        mergeEventData(CB->second);
        for(int i=0;i<root->data.size;++i) {
            uint64_t e;
            GET_TOTAL_DATA_VALUE(e, CB->second, eventData[i]);
            root->data.eventData[i] += e;
        }
    }
}

void splitEnergyData(CallingContextLog* root) {
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        uint64_t energy;
        GET_TOTAL_DATA_VALUE(energy, CB->second, pkg_energy);
        root->data.pkg_energy -= energy;
        splitEnergyData(CB->second);
    }
}

double getTotalTime(CallingContextLog* root) {
    double time = 0;
    if(!root->pruned) {
        uint64_t t;
        GET_TOTAL_DATA_VALUE(t, root, cycle);
        time += t;
    }
    for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        time += getTotalTime(CB->second);
    }
    return time;
}

double getSignificantTime(CallingContextLog* root, double total_time) {
    uint64_t time = 0;
    if(!root->pruned && root->key!=-1) {
        // bool isLeaf = true;
        // for(auto CB=root->children.begin(), CE=root->children.end();CB!=CE;++CB) {
        //     isLeaf = isLeaf && CB->second->pruned;
        // }
        // if(isLeaf) {
            uint64_t t;
            GET_TOTAL_DATA_VALUE(t, root, cycle);
            time += t;
        // }
        // CallingContextLog* p = root;
        // while(p!=NULL) {
        //     printf("%s=>",keyMap[p->key].c_str());
        //     p = p->parent;
        // }
        // printf(";%.2lf\n", (double)root->data.cycle/total_time*100);
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
    // CallingContextLog::print(root);
    //pruneCCTWithThreshold(root, PRUNE_THRESHOLD, false);
    if(options.print_coverage) {
        printf("Significant Coverage : %.2lf %%\n", getSignificantCoverage(root));
    } else {
        root->reset();
        print_significant(root);
        if(warn_count>0) {
            fprintf(stderr, "Total Warn: %d\n", warn_count);
        }
    }
    return 0;
}