import os
import subprocess

def get_metric_name(pre, core, uncore, tnum, comment=None):
    if comment is None:
        return "{0}metric.dat.{1}.{2}.{3}".format(pre,core,uncore,tnum)
    return "{0}metric.dat.{1}.{2}.{3}.{4}".format(pre,core,uncore,tnum, comment)
# execute *exe* with *tnum* threads
# the number of threads will be sent as the last argument of *exe*
# and OMP_NUM_THREADS will automatically set to the tnum
def execute(exe, tnum, core, uncore, keymap_fn, out_dir='./', papi_events=[], cct_fn=None, res_fn=None, enable_freqmod=True, generate_keymap=False, VERBOSE=False, collect_energy=True):
    if res_fn==None:
        res_fn = get_metric_name(out_dir,core, uncore, tnum)
    os.environ.pop('PAETT_DETECT_MODE', 'Not-found')
    os.environ['KMP_AFFINITY']='granularity=fine,compact'
    if tnum>0:
        os.environ['OMP_NUM_THREADS'] = str(tnum)
    else:
        os.environ.pop('OMP_NUM_THREADS', 'Not-found')
    if cct_fn is not None:
        os.environ['PAETT_CCT_FREQUENCY_COMMAND_FILE'] = cct_fn
    else:
        os.environ.pop('PAETT_CCT_FREQUENCY_COMMAND_FILE', 'Not-found')
    os.environ['PAETT_DEFAULT_CORE_FREQ'] = str(core)
    os.environ['PAETT_DEFAULT_UNCORE_FREQ'] = str(uncore)
    if enable_freqmod:
        os.environ['PAETT_ENABLE_FREQMOD'] = 'ENABLE'
    else:
        os.environ['PAETT_ENABLE_FREQMOD'] = 'DISABLE'
    if generate_keymap:
        os.environ['PAETT_KEYMAP_PATH'] = keymap_fn
    else:
        os.environ.pop('PAETT_KEYMAP_PATH', 'Not-found')
    # if PAPI profiling is not needed, we just disable this
    events = ""
    if collect_energy:
        events = "ENERGY;"
    for pe in papi_events:
        events = events + pe + ";"
    # delete last unused ';'
    events = events[:-1]
    os.environ['PAETT_PROFILE_EVENTS'] = events
    if tnum>0:
        exe += " "+str(tnum)
    exe += " > paett-run.log."+str(tnum)
    if VERBOSE:
        print("-- Running: ", exe)
    cmd = "freq_set {0} {1}".format(str(core), str(uncore))
    subprocess.check_call(cmd, shell=True)
    subprocess.check_call("sleep 1", shell=True)
    subprocess.check_call(exe, shell=True)
    subprocess.check_call("rm -rf "+res_fn, shell=True)
    if keymap_fn is not None:
        cmd = "filter_significant_profile --keymap_fn "+keymap_fn + " > " + res_fn
    else:
        cmd = "filter_significant_profile > " + res_fn
    subprocess.check_call(cmd, shell=True)
    return res_fn

# execute *exe* with *tnum* threads, *core* frequency, and *uncore* frequency
# Static execution only collects overall energy consumption
def execute_static(exe, tnum, core, uncore, VERBOSE=False):
    os.environ['KMP_AFFINITY']='granularity=fine,compact'
    if tnum>0:
        os.environ['OMP_NUM_THREADS'] = str(tnum)
    else:
        os.environ.pop('OMP_NUM_THREADS', 'Not-found')
    exe += " > paett-run.log."+str(tnum)
    exe = "collect_energy " + exe
    if VERBOSE:
        print("-- Running: ", exe)
    cmd = "freq_set {0} {1}".format(str(core), str(uncore))
    subprocess.check_call(cmd, shell=True)
    subprocess.check_call("sleep 1", shell=True)
    if tnum>0:
        subprocess.check_call("{0} {1}".format(exe, str(tnum)), shell=True)
    else:
        subprocess.check_call(exe, shell=True)
    with open("collect_energy.log", "r") as f:
        line = f.readline()
        cont = line.split(',')
        energy = float(cont[0].replace(',',''))
        time = float(cont[1].replace(',',''))
    return energy, time

# execute *exe* with *tnum* threads
# the number of threads will be sent as the last argument of *exe*
# and OMP_NUM_THREADS will automatically set to the tnum
def export_execute_script(exe, tnum, core, uncore, keymap_fn, out_dir='./', papi_events=[], cct_fn=None, enable_freqmod=True, generate_keymap=False, VERBOSE=False, collect_energy=True):
    script_content = "#!/bin/bash\n"
    # if res_fn==None:
    #     res_fn = get_metric_name(out_dir,core, uncore, tnum)
    script_content+= "unset PAETT_DETECT_MODE\n"
    script_content+= "export KMP_AFFINITY=granularity=fine,compact\n"
    if tnum>0:
        script_content+= "export OMP_NUM_THREADS={0}\n".format(str(tnum))
    else:
        script_content+= "unset OMP_NUM_THREADS\n"
    if cct_fn is not None:
        script_content+= "export PAETT_CCT_FREQUENCY_COMMAND_FILE={0}\n".format(cct_fn)
    else:
        script_content+= "unset PAETT_CCT_FREQUENCY_COMMAND_FILE\n"
    script_content+= "export PAETT_DEFAULT_CORE_FREQ={0}\n".format(str(core))
    script_content+= "export PAETT_DEFAULT_UNCORE_FREQ={0}\n".format(str(uncore))
    if enable_freqmod:
        script_content+= "export PAETT_ENABLE_FREQMOD=ENABLE\n"
    else:
        script_content+= "export PAETT_ENABLE_FREQMOD=DISABLE\n"
    if generate_keymap:
        script_content+= "export PAETT_KEYMAP_PATH={0}\n".format(keymap_fn)
    else:
        script_content+= "unset PAETT_KEYNAP_PATH\n"
    # if PAPI profiling is not needed, we just disable this
    events = ""
    if collect_energy:
        events = "ENERGY;"
    for pe in papi_events:
        events = events + pe + ";"
    # delete last unused ';'
    events = events[:-1]
    script_content+= "export PAETT_PROFILE_EVENTS={0}\n".format(events)
    exe += " > paett-run.log."+str(tnum)
    cmd = "freq_set {0} {1}".format(str(core), str(uncore))
    script_content+= cmd+"\n"
    script_content+= "sleep 1\n"
    if tnum>0:
        script_content+= "{0} {1}\n".format(exe, str(tnum))
    else:
        script_content+= exe+"\n"
    if VERBOSE:
        print("-- Running: ", exe)
        print(script_content)
    script_fn = "exec-opt.sh"
    with open(script_fn, "w") as f:
        f.write(script_content)
    return script_fn