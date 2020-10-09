from utils.CallingContextTree import CallingContextTree, AdditionalData, load_keyMap
from utils.executor import execute, get_metric_name
from utils.Configuration import Configuration
import argparse
import os
import shutil

import numpy as np

from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import pickle

# For Haswell, only 4 PAPI counters are valid to collect per run.
MAX_PAPI_COUNTER_PER_RUN=4

def get_cct_energy(cct):
    def get_energy(data):
        return data.data[-1]
    return cct.mergeBy(get_energy)

def mergeMetrics(data1, data2):
    return AdditionalData(data1.data[:-1] + data2.data[:-1] + [(float(data1.data[-1])+float(data2.data[-1]))/2])

def reserveMinimalEnergy(data1, data2):
    if data1.data[-1] < data2.data[-1]:
        return data1
    return data2

def addThreadInfo(data, tnum):
    return AdditionalData([tnum]+data.data)

def thread_exec(exe, keymap_fn, tnum, papi, cct, out_dir, enable_continue):
    nrun = int((len(papi) + MAX_PAPI_COUNTER_PER_RUN - 1) / MAX_PAPI_COUNTER_PER_RUN)
    for i in range(0, nrun):
        papi_self = papi[i*MAX_PAPI_COUNTER_PER_RUN:(i+1)*MAX_PAPI_COUNTER_PER_RUN]
        res_fn = get_metric_name(out_dir, config.get_max_core(), config.get_max_uncore(), tnum, i)
        if not (enable_continue or os.path.exists(res_fn)):
            res_fn = execute(exe, tnum, config.get_max_core(), config.get_max_uncore(), keymap_fn, out_dir, res_fn=res_fn, papi_events=papi_self, collect_energy=True)
        file = open(res_fn, 'r')
        cct_tmp = CallingContextTree.load(file)
        file.close()
        if cct is None:
            cct = cct_tmp
        else:
            cct.mergeFrom(cct_tmp, rule=mergeMetrics)
    # Now we add thread information into the data domain
    cct.processAllDataWith(addThreadInfo, tnum)
    return cct

# [start, end], with step size *step*
def thread_search(exe, keymap_fn, papi, start, end, step, enable_consistant_thread, enable_continue, thread_res_fn="thread.cct"):
    out_dir = 'thread_metrics/'
    if enable_continue:
        if not os.path.exists(out_dir):
            print("Warning: continue enabled but no existing output directory found! Disable continue and restart searching.")
            enable_continue = False
            os.mkdir(out_dir)
    else:
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        os.mkdir(out_dir)
    # add single thread execution as baseline
    print("Running with {0} Thread".format(start))
    cct = None
    #cct = thread_exec(exe, keymap_fn, 1, papi, cct, out_dir, enable_continue)
    cct = thread_exec(exe, keymap_fn, start, papi, cct, out_dir, enable_continue)
    energy = get_cct_energy(cct)
    if start==1 and step!=1:
        start = 0
    for i in range(start+step, end+1, step):
        print("Running with {0} Thread".format(i))
        cct_tmp = None
        cct_tmp = thread_exec(exe, keymap_fn, i, papi, cct_tmp, out_dir, enable_continue)
        # thread configuration must be consistant across all ccts
        if enable_consistant_thread:
            etmp = get_cct_energy(cct_tmp)
            if etmp < energy:
                cct = cct_tmp
                energy = etmp
        else:
            cct.mergeFrom(cct_tmp, rule=reserveMinimalEnergy)
    # now cct has already consists of optimal thread number and corresponding PAPI counter values
    # reset cct iterators
    cct.reset()
    if thread_res_fn is not None:
        print("Save thread optimized cct to ", thread_res_fn)
        with open(thread_res_fn, 'w') as f:
            cct.save(f)
    return cct

def make_core(val):
    return val*100000

def make_uncore(val):
    return val*256+val

# [thread, <PAPI counter values>..., energy<not-used>] === <model> ===> [core, uncore, thread]
def predict_frequency(data, args):
    # unpack: data.data = [thread, <PAPI counter values>..., energy<not-used>]
    model = args[0]
    config = args[1]
    papi_num = args[2]
    # the number of metrics is not valid, so ignore this node
    if len(data.data) != 2+papi_num:
        print("Warning: Ignore data:", data, ", as the number of data does not matched user specification!")
        return AdditionalData([0, 0, 0])
    thread = data.data[0]
    metrics = data.data[1:-1]
    inp = []
    for c in range(config.get_min_core(), config.get_max_core()+1):
        for uc in range(config.get_min_uncore(), config.get_max_uncore()+1):
            inp.append([c, uc]+metrics)
    pred = model.predict(np.array(inp))
    j = np.argmin(pred)
    core   = make_core(inp[j][0])
    uncore = make_uncore(inp[j][1])
    return AdditionalData([core, uncore, thread])

def predict_frequency_command_from_model(cct, out_fn, config, model, papi_num):
    cct.processAllDataWith(predict_frequency, [model, config, papi_num])
    with open(out_fn, 'w') as f:
        cct.save(f, delimiter=' ')

def load_model(path):
    model = None
    if os.path.exists(path):
        with open(path, "rb") as f:
            model = pickle.load(f)
    else:
        print("Failed to find model file: '{0}'".format(path))
    return model

def keyToID(key, keyMap):
    #print(key)
    return keyMap[key]

if __name__=='__main__':
    config = Configuration()
    parser = argparse.ArgumentParser(description='Execute scripts to obtain CCT-aware roofline metrics.')
    parser.add_argument('--exe', help='executable compiled with powerspector\'s instrumentation', default='./run.sh')
    parser.add_argument('--keymap', help='keymap generated by the powerspector (with detection mode)', default='PAETT.keymap')
    parser.add_argument('--continue', dest='cont', help='skip execution if the output file is already exist.', action='store_true')
    parser.add_argument('--consistant', help='thread configuration is consistant through all CCTs.', action='store_true')
    #parser.add_argument('--ts', help='start number of threads for searching', type=int, default=2)
    parser.add_argument('--ts', help='start number of threads for searching', type=int, default=1)
    parser.add_argument('--te', help='end number of threads for searching', type=int, default=config.get_max_thread())
    parser.add_argument('--step', help='step of number of threads when searching', type=int, default=2)
    parser.add_argument('--out', help='output file', default='predict.cct')
    parser.add_argument('--model', help='path to dumped pickle sklearn model', default='')
    parser.add_argument('--papi', help='PAPI counters needed for model input, only valid when model is provided. Delimited by ","', default='')
    args = parser.parse_args()
    # initialization
    model = load_model(args.model)
    if model is None:
        print("Error: --model must be specified!")
        exit(1)
    papi_counters = args.papi.split(',')
    print(papi_counters)
    # begin thread searching
    cct = thread_search(args.exe, args.keymap, papi_counters, args.ts, args.te, args.step, args.consistant, args.cont)
    cct.processAllKeyWith(keyToID, load_keyMap(args.keymap))
    predict_frequency_command_from_model(cct, args.out, config, model, len(papi_counters))
