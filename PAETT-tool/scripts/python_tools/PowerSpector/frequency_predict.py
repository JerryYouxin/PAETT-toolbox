from utils.CallingContextTree import CallingContextTree, AdditionalData, load_keyMap
from utils.searcher import threadSearch, thread_exec
from utils.Configuration import config
from utils.executor import execute, get_metric_name
import argparse
import os

import numpy as np

from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import pickle

import shutil

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
    enable_scale = args[3]
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
    trans = np.array(inp)
    if enable_scale:
        trans = StandardScaler().fit_transform(trans)
    pred = model.predict(trans)
    j = np.argmin(pred)
    core   = make_core(inp[j][0])
    uncore = make_uncore(inp[j][1])
    return AdditionalData([core, uncore, thread])

# predict frequency command from model
def predict(cct, out_fn, config, model, papi_num, enable_scale):
    cct.processAllDataWith(predict_frequency, [model, config, papi_num, enable_scale])
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

def keyToID_lx(key, keyMap):
    ID = keyMap[key]
    if ID < 0:
        ID = pow(2, 64) + ID
    return str(hex(ID)[2:])

def predict_region_frequency(model, coreList, uncoreList, metrics, enable_scale):
    inp = []
    for c in coreList:
        for uc in uncoreList:
            inp.append([c, uc]+metrics)
    trans = np.array(inp)
    if enable_scale:
        trans = StandardScaler().fit_transform(trans)
    pred = model.predict(trans)
    j = np.argmin(pred)
    core   = make_core(inp[j][0])
    uncore = make_uncore(inp[j][1])
    return core, uncore

def getTnumList(ts, te, step):
    tnumList = []
    if ts==1:
        tnumList.append(ts)
        ts = 2
    for t in range(ts, te, step):
        tnumList.append(t)
    return tnumList

# tnum, core, uncore: -1 indicates iterating all possible configurations; 0 indicates using default; >0 indicates the specified configuration
def region_frequency_predict(keymap_fn, model, papi, enable_scale, tnumList=None, coreList=None, uncoreList=None, VERBOSE=1):
    out_dir = 'thread_metrics/'
    if not os.path.exists(out_dir):
        print("Error: no existing output directory found! Something may go wrong during thread searching!")
        exit(1)
    if coreList is None:
        coreList = [ i for i in range(config.get_min_core(), config.get_max_core()+1) ]
    if uncoreList is None:
        uncoreList = [ i for i in range(config.get_min_uncore(), config.get_max_uncore()+1) ]
    if tnumList is None:
        tnumList = [ i for i in range(1, config.get_max_thread()+1) ]
    data = {}
    print("Thread:", tnumList)
    print("Core  :", coreList)
    print("Uncore:", uncoreList)
    totSearch = len(tnumList)
    keyMap = load_keyMap(keymap_fn)
    num = 0.0
    for t in tnumList:
        c = config.get_max_core()
        u = config.get_max_uncore()
        if VERBOSE>1:
            print("Running with {0} thread, {1} core, {2} uncore".format(t,c,u))
        else:
            print("\r[{0:3.1%}] Running with {1} thread, {2} core, {3} uncore".format(num/totSearch,t,c,u), end='')
            num += 1
        cct_tmp = None
        cct_tmp = thread_exec(exe=None, keymap_fn=keymap_fn, tnum=t, papi=papi, cct=cct_tmp, out_dir=out_dir, enable_continue=True)
        cct_tmp.processAllDataWith(lambda dat:AdditionalData([float(d) for d in dat.data[1:]]))
        # cct_tmp.print()
        # extract to list
        lst = cct_tmp.extractToList(False)
        for cont in lst:
            if cont[0] in data.keys():
                if cont[-1] < data[cont[0]][0]:
                    data[cont[0]] = [ cont[-1], t, cont[1:-1] ]
            else:
                data[cont[0]] = [ cont[-1], t, cont[1:-1] ]
    print("\r[{0:3.1%}] Finish Thread searching".format(1))
    freqComm = []
    num = 0.0
    totPredict = len(data)
    # predict as region-based frequency command
    for key, dat in data.items():
        if VERBOSE>1:
            print("Predict region: {0}".format(key))
        else:
            print("\r[{0:3.1%}] Predict region: {1}".format(num/totPredict,key), end='')
            num += 1
        thread = dat[1]
        metrics = dat[2]
        print(thread, metrics)
        core, uncore = predict_region_frequency(model, coreList, uncoreList, metrics, enable_scale)
        freqComm.append(keyToID_lx(key, keyMap) + " " + key + ";" + str(core) + " " + str(uncore) + " " + str(thread) + " 0 0 0\n")
    print("\n[{0:3.1%}] Prediction Finish!".format(1))
    return freqComm

def main():
    parser = argparse.ArgumentParser(description='Execute scripts to generate CCT-aware frequency commands with model prediction.')
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
    parser.add_argument('--papi', help='PAPI counters needed for model input, only valid when model is provided. Delimited by ","', default='PAPI_BR_NTK,PAPI_LD_INS,PAPI_L2_ICR,PAPI_BR_MSP,PAPI_RES_STL,PAPI_SR_INS,PAPI_L2_DCR')
    parser.add_argument('--disable-scale', help="Disable scaling the input metric with StdScaler.", action="store_true")
    parser.add_argument('--region-based', help='Region based model prediction for optimal frequency commands. Need re-compile to apply this region-based commands.', action='store_true')
    args = parser.parse_args()
    enable_scale = True
    if args.disable_scale:
        enable_scale = False
    # initialization
    model = load_model(args.model)
    if model is None:
        print("Error: --model must be specified!")
        exit(1)
    papi_counters = args.papi.split(',')
    print(papi_counters)
    if args.region_based:
        args.out = "paett_model.cache"
        print("The generated frequency commands will be written into: ", args.out)
        with open(args.out, "w") as f:
            best_thread = threadSearch(args.exe, args.keymap, papi_counters, args.ts, args.te, args.step, args.consistant, args.cont, generate_commands=True, cct_file='thread.cct')
            if args.consistant:
                data = region_frequency_predict(args.keymap, model, papi_counters, enable_scale, tnumList=[best_thread])
            else:
                tnumList = getTnumList(args.ts, args.te, args.step)
                data = region_frequency_predict(args.keymap, model, papi_counters, enable_scale, tnumList=tnumList)
            f.writelines(data)
    else:
        # begin thread searching
        cct = threadSearch(args.exe, args.keymap, papi_counters, args.ts, args.te, args.step, args.consistant, args.cont, enable_cct=True)
        cct.processAllKeyWith(keyToID, load_keyMap(args.keymap))
        predict(cct, args.out, config, model, len(papi_counters), enable_scale)

if __name__=='__main__':
    main()
