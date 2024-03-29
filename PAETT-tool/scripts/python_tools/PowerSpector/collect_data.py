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

def convert_format(format):
    format=format.replace('<thread>', '{0}')
    format=format.replace('<core>'  , '{1}')
    format=format.replace('<uncore>', '{2}')
    format=format.replace('<papi>'  , '{3}')
    format=format.replace('<cycle>' , '{4}')
    format=format.replace('<energy>', '{5}')
    return format

def write_metrics(f, data, format="<thread> <core> <uncore> <papi> <cycle> <energy>"):
    for cont in data:
        c = cont[1]
        u = cont[2]
        t = cont[3]
        cycle = cont[-2]
        energy = cont[-1]
        papi = ""
        if len(cont)>6:
            for v in cont[4:-2]:
                papi += str(v)+' '
            papi = papi[:-1]
        buff = cont[0]+';' + convert_format(format).format(t, c, u, papi, cycle, energy)
        f.write(buff+'\n')

# tnum, core, uncore: -1 indicates iterating all possible configurations; 0 indicates using default; >0 indicates the specified configuration
def collectData(exe, keymap_fn, tnum, core, uncore, papi=[], cct_file=None, check_point_dir=None, collect_energy=True, enable_cct=True, enable_continue=False, VERBOSE=1):
    print("The checkpoint directory is set to: ", check_point_dir)
    if check_point_dir is not None:
        if enable_continue:
            if not os.path.exists(check_point_dir):
                print("Warning: continue enabled but no existing output directory found! Disable continue and restart searching.")
                enable_continue = False
                os.mkdir(check_point_dir)
        else:
            if os.path.exists(check_point_dir):
                shutil.rmtree(check_point_dir)
            os.mkdir(check_point_dir)
    out_dir = 'metrics/'
    if enable_continue:
        if not os.path.exists(out_dir):
            print("Warning: continue enabled but no existing output directory found! Disable continue and restart searching.")
            enable_continue = False
            os.mkdir(out_dir)
    else:
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        os.mkdir(out_dir)
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
                        res_fn = execute(exe, t, c, u, keymap_fn, out_dir, res_fn=res_fn, papi_events=papi_self, collect_energy=True, cct_fn=cct_file)
                    file = open(res_fn, 'r')
                    __cct_tmp = CallingContextTree.load(file)
                    file.close()
                    if cct_tmp is None:
                        cct_tmp = __cct_tmp
                    else:
                        cct_tmp.mergeFrom(__cct_tmp, rule=mergeMetrics)
                # Now we add thread information into the data domain
                # If t, u, c=0, the thread number information is not needed by the user
                # if t>0:
                cct_tmp.processAllDataWith(addThreadInfo, t)
                # if u>0:
                cct_tmp.processAllDataWith(addThreadInfo, u)
                # if c>0:
                cct_tmp.processAllDataWith(addThreadInfo, c)
                # extract to list
                lst = cct_tmp.extractToList(enable_cct)
                if check_point_dir is not None:
                    with open(check_point_dir+'/metric.{0}.{1}.{2}'.format(t,u,c), "w") as f:
                        write_metrics(f, lst)
                data += lst
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
    parser.add_argument('--format', help='output format of metrics, including <thread> <core> <uncore> <papi> <cycle> <energy>', default='<core> <uncore> <papi> <energy>')
    parser.add_argument('--target', help='collect target: energy, edp', default='energy')
    args = parser.parse_args()

    check_point_dir = args.out.split('/')
    if len(check_point_dir) > 1:
        check_point_dir = "/".join(check_point_dir[:-1])
    else:
        check_point_dir = './'
    check_point_dir = check_point_dir+'/checkpoints/'

    papi = args.papi.split(',')
    assert(len(papi)>0)
    with open(args.out, "w") as f:
        print("The collected data will be written into: ", args.out)
        best_thread = threadSearch(args.exe, args.keymap, [], args.ts, args.te, args.step, args.consistant, args.cont, target=args.target, generate_commands=True, cct_file='thread.cct')
        if args.consistant:
            data = collectData(args.exe, args.keymap, best_thread, -1, -1, enable_continue=args.cont, papi=papi, check_point_dir=check_point_dir)
        else:
            data = collectData(args.exe, args.keymap, 0, -1, -1, cct_file='thread.cct', enable_continue=args.cont, papi=papi, check_point_dir=check_point_dir)
        write_metrics(f, data, args.format)

if __name__=='__main__':
    main()