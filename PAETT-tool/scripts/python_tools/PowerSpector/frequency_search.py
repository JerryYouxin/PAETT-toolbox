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

def make_core(c):
    return c*100000

def make_uncore(u):
    return u*256+u

def convert_format(format):
    print("before: ", format)
    format = format.replace('<thread>', '{0}')
    format = format.replace('<core>'  , '{1}')
    format = format.replace('<uncore>', '{2}')
    format = format.replace('<papi>'  , '{3}')
    format = format.replace('<energy>', '{4}')
    print("after : ", format)
    return format

def write_metrics(f, data, format="<thread> <core> <uncore> <papi> <energy>"):
    for cont in data:
        c = cont[1]
        u = cont[2]
        t = cont[3]
        energy = cont[-1]
        papi = ""
        if len(cont)>5:
            for v in cont[4:-1]:
                papi += str(v)+' '
            papi = papi[:-1]
        buff = cont[0]+';' + convert_format(format).format(t, c, u, papi, energy)
        f.write(buff+'\n')

def keyToID_lx(key, keyMap):
    ID = keyMap[key]
    if ID < 0:
        ID = pow(2, 64) + ID
    return str(hex(ID)[2:])

# tnum, core, uncore: -1 indicates iterating all possible configurations; 0 indicates using default; >0 indicates the specified configuration
def region_frequency_search(exe, keymap_fn, tnum, core, uncore, cct_file=None, collect_energy=True, enable_continue=False, VERBOSE=1):
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
    data = {}
    keyMap = load_keyMap(keymap_fn)
    print("Thread:", tnumList)
    print("Core  :", coreList)
    print("Uncore:", uncoreList)
    tot = len(tnumList)*len(coreList)*len(uncoreList)
    num = 0.0
    # ignoreLst = []
    for t in tnumList:
        for c in coreList:
            for u in uncoreList:
                if VERBOSE>1:
                    print("Running with {0} thread, {1} core, {2} uncore".format(t,c,u))
                else:
                    print("[{0:.1%}] Running with {1} thread, {2} core, {3} uncore".format(num/tot,t,c,u), end='\r')
                    num += 1
                cct_tmp = None
                res_fn = get_metric_name(out_dir, c, u, t, 0)
                if (not os.path.exists(res_fn)) and os.path.exists('.'.join(res_fn.split('.')[:-1])):
                    res_fn = '.'.join(res_fn.split('.')[:-1])
                if not (enable_continue or os.path.exists(res_fn)):
                    print("FETAL ERROR: metrics not found!")
                    exit(1)
                    # res_fn = execute(exe, t, c, u, keymap_fn, out_dir, res_fn=res_fn, collect_energy=True, cct_fn=cct_file)
                file = open(res_fn, 'r')
                cct_tmp = CallingContextTree.load(file)
                cct_tmp.processAllDataWith(lambda dat:AdditionalData([float(d) for d in dat.data]))
                file.close()
                # extract to list
                lst = cct_tmp.extractToList(False)
                for cont in lst:
                    if cont[0] in data.keys():
                        if cont[-1] < data[cont[0]][0]:
                            data[cont[0]][0] = cont[-1]
                            data[cont[0]][1] = keyToID_lx(cont[0], keyMap) + " " + cont[0] + ";" + str(make_core(c)) + " " + str(make_uncore(u)) + " " + str(t) + " 0 0 0\n"
                    else:
                        data[cont[0]] = [ cont[-1], 
                                          keyToID_lx(cont[0], keyMap) + " " + cont[0] + ";" + str(make_core(c)) + " " + str(make_uncore(u)) + " " + str(t) + " 0 0 0\n" 
                                          ]
    # extract to list
    freqComm = []
    for key, d in data.items():
        freqComm.append(d[1])
    print("\nFinish!")
    return freqComm

def main():
    default_step = 1
    if config.get_max_thread() > 10:
        default_step = 2
    parser = argparse.ArgumentParser(description='Execute scripts to search for optimal region-based frequency commands.')
    parser.add_argument('--exe', help='executable compiled with powerspector\'s instrumentation', default='./run.sh')
    parser.add_argument('--keymap', help='keymap generated by the powerspector (with detection mode)', default='PAETT.keymap')
    parser.add_argument('--continue', dest='cont', help='skip execution if the output file is already exist.', action='store_true')
    parser.add_argument('--consistant', help='thread configuration is consistant through all CCTs.', action='store_true')
    parser.add_argument('--ts', help='start number of threads for searching', type=int, default=1)
    parser.add_argument('--te', help='end number of threads for searching', type=int, default=config.get_max_thread())
    parser.add_argument('--step', help='step of number of threads when searching', type=int, default=default_step)
    parser.add_argument('--out', help='output file', default='paett_model.cache')
    args = parser.parse_args()

    if not args.cont:
        print("FETAL ERROR: Currently, we only support searching for frequency commands from collected data. Please run collect_data first")
        exit(1)

    print("The generated frequency commands will be written into: ", args.out)
    with open(args.out, "w") as f:
        best_thread = threadSearch(args.exe, args.keymap, [], args.ts, args.te, args.step, args.consistant, args.cont, generate_commands=True, cct_file='thread.cct')
        if args.consistant:
            data = region_frequency_search(args.exe, args.keymap, best_thread, -1, -1, enable_continue=args.cont)
        else:
            data = region_frequency_search(args.exe, args.keymap, 0, -1, -1, cct_file='thread.cct', enable_continue=args.cont)
        f.writelines(data)

if __name__=='__main__':
    main()