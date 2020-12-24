from utils.CallingContextTree import CallingContextTree, AdditionalData, load_keyMap
from utils.executor import execute, get_metric_name
from utils.Configuration import config
from utils.searcher import threadSearch, mergeMetrics, addThreadInfo

import os
import shutil
import numpy as np
import argparse

# For Haswell, only 4 PAPI counters are valid to collect per run.
MAX_PAPI_COUNTER_PER_RUN=4

# tnum, core, uncore: -1 indicates iterating all possible configurations; 0 indicates using default; >0 indicates the specified configuration
def collectData(exe, keymap_fn, tnum, core, uncore, papi=[], cct_file=None, cct=None, collect_energy=True, enable_cct=True, enable_continue=False, VERBOSE=1):
    out_dir = "metrics/"
    if enable_continue:
        if not os.path.exists(out_dir):
            print("Warning: continue enabled but no existing output directory found! Disable continue and restart searching.")
            enable_continue = False
            os.mkdir(out_dir)
    else:
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        os.mkdir(out_dir)
    if cct_file is not None:
        with open(cct_file, "r") as f:
            cct = CallingContextTree.load(f)
    tnumList = []
    coreList = []
    uncoreList = []
    if core>=0:
        coreList.append(core)
    else:
        coreList = [ i for i in range(config.get_min_core(), config.get_max_core()+1) ]
    if uncore>=0:
        uncoreList.append(uncore)
    else:
        uncoreList = [ i for i in range(config.get_min_uncore(), config.get_max_uncore()+1) ]
    if tnum>=0:
        tnumList.append(tnum)
    else:
        tnumList = [ i for i in range(1, config.get_max_thread()+1) ]
    data = []
    print("Thread:", tnumList)
    print("Core  :", coreList)
    print("Uncore:", uncoreList)
    print("PAPI  :", papi)
    tot = len(tnumList)*len(coreList)*len(uncoreList)
    num = 0.0
    for t in tnumList:
        for c in coreList:
            for u in uncoreList:
                if VERBOSE>1:
                    print("Running with {0} thread, {1} core, {2} uncore".format(t,c,u))
                else:
                    print("[{0:.1%}] Running with {1} thread, {2} core, {3} uncore".format(num/tot,t,c,u), end='\r')
                    num += 1
                cct_tmp = None
                nrun = int((len(papi) + MAX_PAPI_COUNTER_PER_RUN - 1) / MAX_PAPI_COUNTER_PER_RUN)
                for i in range(0, nrun):
                    papi_self = papi[i*MAX_PAPI_COUNTER_PER_RUN:(i+1)*MAX_PAPI_COUNTER_PER_RUN]
                    res_fn = get_metric_name(out_dir, c, u, t, i)
                    if not (enable_continue or os.path.exists(res_fn)):
                        res_fn = execute(exe, t, c, u, keymap_fn, out_dir, res_fn=res_fn, papi_events=papi_self, collect_energy=True)
                    file = open(res_fn, 'r')
                    __cct_tmp = CallingContextTree.load(file)
                    file.close()
                    if cct_tmp is None:
                        cct_tmp = __cct_tmp
                    else:
                        cct_tmp.mergeFrom(__cct_tmp, rule=mergeMetrics)
                # Now we add thread information into the data domain
                # If t, u, c=0, the thread number information is not needed by the user
                if t>0:
                    cct_tmp.processAllDataWith(addThreadInfo, t)
                if u>0:
                    cct_tmp.processAllDataWith(addThreadInfo, u)
                if c>0:
                    cct_tmp.processAllDataWith(addThreadInfo, c)
                # extract to list
                data += cct_tmp.extractToList(enable_cct)
    print("\nFinish!")
    return data

def main():
    default_step = 1
    if config.get_max_thread() > 10:
        default_step = 2
    parser = argparse.ArgumentParser(description='Execute scripts to collect CCT-aware metrics.')
    parser.add_argument('--exe', help='executable compiled with powerspector\'s instrumentation', default='./run.sh')
    parser.add_argument('--keymap', help='keymap generated by the powerspector (with detection mode)', default='PAETT.keymap')
    parser.add_argument('--continue', dest='cont', help='skip execution if the output file is already exist.', action='store_true')
    parser.add_argument('--consistant', help='thread configuration is consistant through all CCTs.', action='store_true')
    #parser.add_argument('--ts', help='start number of threads for searching', type=int, default=2)
    parser.add_argument('--ts', help='start number of threads for searching', type=int, default=1)
    parser.add_argument('--te', help='end number of threads for searching', type=int, default=config.get_max_thread())
    parser.add_argument('--step', help='step of number of threads when searching', type=int, default=default_step)
    parser.add_argument('--out', help='output file', default='metric.out')
    parser.add_argument('--papi', help='PAPI counters needed for model input, only valid when model is provided. Delimited by ","', default='')
    args = parser.parse_args()

    papi = args.papi.split(',')
    assert(len(papi)>0)
    with open(args.out, "w") as f:
        print("The collected data will be written into: ", args.out)
        cct = threadSearch(args.exe, args.keymap, args.papi.split(','), args.ts, args.te, args.step, args.consistant, args.cont)
        data = collectData(args.exe, args.keymap, 0, -1, -1, cct=cct, enable_continue=args.cont, papi=papi)
        for cont in data:
            buff = cont[0]+';'
            if len(cont)>2:
                for v in cont[1:-1]:
                    buff += str(v)+' '
            buff += str(cont[-1])
            f.write(buff+'\n')

if __name__=='__main__':
    main()