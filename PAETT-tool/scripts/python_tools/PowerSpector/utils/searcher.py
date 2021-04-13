from .CallingContextTree import CCTFrequencyCommand, CallingContextTree, AdditionalData, load_keyMap
from .executor import execute, execute_static, get_metric_name
from .Configuration import config

import os
import shutil

MAX_PAPI_COUNTER_PER_RUN=4

def get_cct_energy(cct):
    def get_energy(data):
        return float(data.data[-1])
    return cct.mergeBy(get_energy)

def mergeMetrics(data1, data2):
    return AdditionalData(data1.data[:-1] + data2.data[:-1] + [(float(data1.data[-1])+float(data2.data[-1]))/2])

def reserveMinimalEnergy(data1, data2):
    if data1.data[-1] < data2.data[-1]:
        return data1
    return data2

def addThreadInfo(data, tnum):
    return AdditionalData([tnum]+data.data)

def thread_exec(exe, keymap_fn, tnum, papi, cct, out_dir, enable_continue, enable_freqmod=True):
    if len(papi)>0:
        nrun = int((len(papi) + MAX_PAPI_COUNTER_PER_RUN - 1) / MAX_PAPI_COUNTER_PER_RUN)
        for i in range(0, nrun):
            papi_self = papi[i*MAX_PAPI_COUNTER_PER_RUN:(i+1)*MAX_PAPI_COUNTER_PER_RUN]
            res_fn = get_metric_name(out_dir, config.get_max_core(), config.get_max_uncore(), tnum, i)
            if not (enable_continue or os.path.exists(res_fn)):
                res_fn = execute(exe, tnum, config.get_max_core(), config.get_max_uncore(), keymap_fn, out_dir, res_fn=res_fn, papi_events=papi_self, collect_energy=True, enable_freqmod=enable_freqmod)
            file = open(res_fn, 'r')
            cct_tmp = CallingContextTree.load(file)
            file.close()
            if cct is None:
                cct = cct_tmp
            else:
                cct.mergeFrom(cct_tmp, rule=mergeMetrics)
    else:
        res_fn = get_metric_name(out_dir, config.get_max_core(), config.get_max_uncore(), tnum, 0)
        if (not os.path.exists(res_fn)) and os.path.exists('.'.join(res_fn.split('.')[:-1])):
            res_fn = '.'.join(res_fn.split('.')[:-1])
        if not (enable_continue or os.path.exists(res_fn)):
            res_fn = execute(exe, tnum, config.get_max_core(), config.get_max_uncore(), keymap_fn, out_dir, res_fn=res_fn, papi_events=[], collect_energy=True, enable_freqmod=enable_freqmod)
        file = open(res_fn, 'r')
        cct = CallingContextTree.load(file)
        file.close()
    # Now we add thread information into the data domain
    cct.processAllDataWith(addThreadInfo, tnum)
    return cct

# [start, end], with step size *step*
def threadSearch(exe, keymap_fn, papi, start, end, step, enable_consistant_thread, enable_continue, enable_cct=False, cct_file="thread.cct", generate_commands=False, checkpoint_dir='./'):
    out_dir = checkpoint_dir+'/thread_metrics/'
    print("Using checkpoint directory: ", out_dir)
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
    print("Running with {0} Thread: ".format(start), end='', flush=True)
    cct = None
    #cct = thread_exec(exe, keymap_fn, 1, papi, cct, out_dir, enable_continue)
    cct = thread_exec(exe, keymap_fn, start, papi, cct, out_dir, enable_continue)
    energy = get_cct_energy(cct)
    best_thread = start
    print("Energy {0} Joules".format(energy))
    if start==1 and step!=1:
        start = 0
    for i in range(start+step, end+1, step):
        print("Running with {0} Thread: ".format(i), end='', flush=True)
        cct_tmp = None
        cct_tmp = thread_exec(exe, keymap_fn, i, papi, cct_tmp, out_dir, enable_continue)
        # thread configuration must be consistant across all ccts
        if enable_consistant_thread:
            etmp = get_cct_energy(cct_tmp)
            print("Energy {0} Joules".format(etmp))
            if etmp < energy:
                cct = cct_tmp
                energy = etmp
                best_thread = i
                print("Update Best as ", i)
        else:
            cct.mergeFrom(cct_tmp, rule=reserveMinimalEnergy)
            print("Energy {0} Joules".format(get_cct_energy(cct)))
    # now cct has already consists of optimal thread number and corresponding PAPI counter values
    # reset cct iterators
    cct.reset()
    if cct_file is not None:
        if generate_commands:
            print("Save thread optimized cct frequency commands to ", cct_file)
            cct.processAllKeyWith(lambda key,keyMap:keyMap[key], load_keyMap(keymap_fn))
            cct.processAllDataWith(lambda data:AdditionalData([0,0,data.data[0]]))
            with open(cct_file, 'w') as f:
                cct.save(f, delimiter=' ')
        else:
            print("Save thread optimized cct to ", cct_file)
            with open(cct_file, 'w') as f:
                cct.save(f)
    if not enable_cct:
        return best_thread
    return cct
