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

def thread_exec(exe, keymap_fn, tnum, papi, cct, out_dir, enable_continue):
    if len(papi)>0:
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
    else:
        res_fn = get_metric_name(out_dir, config.get_max_core(), config.get_max_uncore(), tnum, 0)
        res_fn = execute(exe, tnum, config.get_max_core(), config.get_max_uncore(), keymap_fn, out_dir, res_fn=res_fn, papi_events=[], collect_energy=True)
        file = open(res_fn, 'r')
        cct = CallingContextTree.load(file)
        file.close()
    # Now we add thread information into the data domain
    cct.processAllDataWith(addThreadInfo, tnum)
    return cct

# [start, end], with step size *step*
def threadSearch(exe, keymap_fn, papi, start, end, step, enable_consistant_thread, enable_continue, enable_cct=True, cct_file="thread.cct", generate_commands=False, checkpoint_dir='./'):
    assert(enable_cct==True)
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
                print("Update Best as ", i)
        else:
            cct.mergeFrom(cct_tmp, rule=reserveMinimalEnergy)
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
    return cct

class StaticThreadSearcher: 
    def __init__(self, exe, begin, end, step, verbose):
        self.exe = exe
        self.begin = begin
        if self.begin==1:
            self.begin += step
        self.end = end
        self.step = step
        self.verb = verbose
    
    def run(self):
        tnum = 1
        core = config.get_max_core()
        uncore = config.get_max_uncore()
        emin, _ = execute_static(self.exe, tnum, core, uncore, self.verb)
        for t in range(self.begin, self.end+1, self.step):
            if self.verb:
                print("Running with thread={0}, core={1}, uncore={2}".format(t, core, uncore))
            energy, _ = execute_static(self.exe, t, core, uncore, self.verb)
            if emin>energy:
                tnum = t
                emin = energy
        return tnum

class ThreadSearcher:
    def __init__(self, exe, keymap_fn, papi, start, end, step, verbose, enable_consistant_thread, enable_continue, enable_cct=True, cct_file="thread.cct"):
        self.exe = exe
        self.keymap_fn = keymap_fn
        self.papi = papi
        self.start = start
        self.end = end
        self.step = step
        self.verb = verbose
        self.enable_cct=enable_cct
        self.cct_file=cct_file
        self.enable_continue=enable_continue
        self.enable_consistant_thread = enable_consistant_thread
        assert(enable_cct==True)

    def run(self):
        out_dir = 'thread_metrics/'
        if self.enable_continue:
            if not os.path.exists(out_dir):
                print("Warning: continue enabled but no existing output directory found! Disable continue and restart searching.")
                self.enable_continue = False
                os.mkdir(out_dir)
        else:
            if os.path.exists(out_dir):
                shutil.rmtree(out_dir)
            os.mkdir(out_dir)
        # add single thread execution as baseline
        print("Running with {0} Thread".format(self.start))
        cct = None
        #cct = thread_exec(exe, keymap_fn, 1, papi, cct, out_dir, enable_continue)
        cct = thread_exec(self.exe, self.keymap_fn, self.start, self.papi, cct, out_dir, self.enable_continue)
        energy = get_cct_energy(cct)
        start = self.start
        if start==1 and self.step!=1:
            start = 0
        start+= self.step
        for i in range(start, self.end+1, self.step):
            print("Running with {0} Thread".format(i))
            cct_tmp = None
            cct_tmp = thread_exec(self.exe, self.keymap_fn, i, self.papi, cct_tmp, out_dir, self.enable_continue)
            # thread configuration must be consistant across all ccts
            if self.enable_consistant_thread:
                etmp = get_cct_energy(cct_tmp)
                if etmp < energy:
                    cct = cct_tmp
                    energy = etmp
            else:
                cct.mergeFrom(cct_tmp, rule=reserveMinimalEnergy)
        # now cct has already consists of optimal thread number and corresponding PAPI counter values
        # reset cct iterators
        cct.reset()
        if self.cct_file is not None:
            print("Save thread optimized cct to ", self.cct_file)
            with open(self.cct_file, 'w') as f:
                cct.save(f)
        return cct


class StaticSearcher:
    def __init__(self, exe, begin, end, step, VERBOSE=True):
        print("[Info] Use Static searching")
        self.verb = VERBOSE
        self.exe = exe
        self.tsearcher = StaticThreadSearcher(exe, begin, end, step, VERBOSE)

    def run(self):
        tnum = self.tsearcher.run()
        emin = None
        core = None
        uncore = None
        for c in range(config.get_min_core(),config.get_max_core()+1):
            for uc in range(config.get_min_uncore(), config.get_max_uncore()+1):
                if self.verb:
                    print("Running with thread={0}, core={1}, uncore={2}".format(tnum, c, uc))
                energy, time = execute_static(self.exe, tnum, c, uc, self.verb)
                if (emin is None) or (emin>energy):
                    core = c
                    uncore = uc
                    emin = energy
                    if self.verb:
                        print("-- Update to thread={0} core={1} uncore={2}: energy={3}, time={4}".format(tnum, core, uncore, energy, time))
        return tnum, core, uncore

class ExaustiveSearcher:
    def __init__(self, exe, keymap_fn, papi, start, end, step, out_fn="frequency_command", verbose=True, enable_consistant=True, enable_continue=True, enable_cct=True):
        print("[Info] Use Exaustive searching")
        self.verb = verbose
        self.exe = exe
        self.tsearcher = ThreadSearcher(exe, keymap_fn, papi, start, end, step, verbose, enable_consistant, enable_continue, enable_cct)

    def run(self):
        cct = self.tsearcher.run()

        return cct

class Searcher:
    def __init__(self, exe, keymap_fn="PAETT.keymap", papi=[], tbegin=None, tend=None, tstep=None, method="exaustive", thread_only=False, verbose=True, enable_consistant=True, enable_continue=True):
        if thread_only:
            print("[Info] Thread Search Enabled")
        if method=="exaustive":
            if thread_only:
                self.searcher = ThreadSearcher(exe, keymap_fn, papi, tbegin, tend, tstep, verbose, enable_consistant, enable_continue)
            else:
                self.searcher = ExaustiveSearcher(exe, keymap_fn, papi, tbegin, tend, tstep, verbose, enable_consistant, enable_continue)
        elif method=="static":
            print("Searching for optimal static configuration...")
            if thread_only:
                self.searcher = StaticThreadSearcher(exe, tbegin, tend, tstep, verbose)
            else:
                self.searcher = StaticSearcher(exe, tbegin, tend, tstep, verbose)
        else:
            raise ValueError("Unknown Method: " + method)

    def run(self):
        self.searcher.run()