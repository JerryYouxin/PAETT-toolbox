from utils.CallingContextTree import CallingContextTree, AdditionalData, load_keyMap
from utils.executor import execute, get_metric_name
from utils.Configuration import Configuration

import os
import shutil
import numpy as np

# For Haswell, only 4 PAPI counters are valid to collect per run.
MAX_PAPI_COUNTER_PER_RUN=4
config = Configuration()

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
def threadSearch(exe, keymap_fn, papi, start, end, step, enable_consistant_thread, enable_continue, enable_cct=True, cct_file="thread.cct"):
    assert(enable_cct==True)
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
    if cct_file is not None:
        print("Save thread optimized cct to ", cct_file)
        with open(cct_file, 'w') as f:
            cct.save(f)
    return cct

# tnum, core, uncore: -1 indicates iterating all possible configurations; 0 indicates using default; >0 indicates the specified configuration
def collectData(exe, keymap_fn, tnum, core, uncore, papi=[], cct_file=None, collect_energy=True, enable_cct=True, enable_continue=False):
    out_dir = "metrics"
    if enable_continue:
        if not os.path.exists(out_dir):
            print("Warning: continue enabled but no existing output directory found! Disable continue and restart searching.")
            enable_continue = False
            os.mkdir(out_dir)
    else:
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        os.mkdir(out_dir)
    cct = None
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
    for t in tnumList:
        for c in coreList:
            for u in uncoreList:
                print("Running with {0} thread, {1} core, {2} uncore".format(t,c,u))
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
                cct_tmp.processAllDataWith(addThreadInfo, tnum)
                cct_tmp.processAllDataWith(addThreadInfo, uncore)
                cct_tmp.processAllDataWith(addThreadInfo, core)
                # extract to list
                data += cct_tmp.extractToList(enable_cct)
    return data

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

def predict(cct, out_fn, config, model, papi_num):
    cct.processAllDataWith(predict_frequency, [model, config, papi_num])
    with open(out_fn, 'w') as f:
        cct.save(f, delimiter=' ')