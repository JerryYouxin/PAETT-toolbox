from utils.CallingContextTree import CallingContextTree, AdditionalData
from utils.executor import execute, get_metric_name
from utils.Configuration import Configuration
import argparse
import os

minMetrics = [-1,-1,-1]
maxMetrics = [0,0,0]
def rawToMetric(raw):
    # 'PAPI_TOT_INS', 'PAPI_TOT_CYC', 'PAPI_LD_INS', 'PAPI_SR_INS'
    AVXIns = int(raw.data[0])
    L3_TCM = int(raw.data[1])
    L2_LINE_IN = int(raw.data[2])
    BR_CN = int(raw.data[3])
    return AdditionalData([AVXIns/float(L3_TCM), L2_LINE_IN, BR_CN])

def getMinMaxMetrics(raw):
    for i in range(0,3):
        if minMetrics[i]==-1:
            minMetrics[i] = raw.data[i]
        else:
            minMetrics[i] = min(minMetrics[i], raw.data[i])
        maxMetrics[i] = max(maxMetrics[i], raw.data[i])
    return raw

def normalizeMetrics(raw):
    x = []
    for i in range(0,3):
        x.append((raw.data[i]-minMetrics[i])/(maxMetrics[i]-minMetrics[i]))
    return AdditionalData(x)

if __name__=='__main__':
    config = Configuration()
    parser = argparse.ArgumentParser(description='Execute scripts to obtain CCT-aware roofline metrics.')
    parser.add_argument('--exe', help='executable compiled with powerspector\'s instrumentation', default='run.sh')
    parser.add_argument('--keymap', help='keymap generated by the powerspector (with detection mode)', default='PAETT.keymap')
    parser.add_argument('--continue', help='skip execution if the output file is already exist.', action='store_true')
    parser.add_argument('--out', help='output directory', default='./')
    args = parser.parse_args()
    resFn = get_metric_name(args.out,config.get_max_core(), config.get_max_uncore(), config.get_max_thread())
    if not os.path.exists(resFn):
        # PAPI events from Madhura and Michael, ICPP workshop 2020 
        resFn = execute(args.exe, 
                    out_dir=args.out,
                    core=config.get_max_core(), 
                    uncore=config.get_max_uncore(), 
                    tnum=config.get_max_thread(), 
                    keymap_fn=args.keymap, 
                    collect_energy=False, 
                    enable_freqmod=False, 
                    papi_events=
                        ['perf_raw::r04C6', 'PAPI_L3_TCM', 'L2_LINES_IN.ANY', 'PAPI_BR_CN']
                    )
    file = open(resFn, 'r')
    cct = CallingContextTree.load(file)
    file.close()
    cct.processAllDataWith(rawToMetric)
    cct.processAllDataWith(getMinMaxMetrics)
    cct.processAllDataWith(normalizeMetrics)
    cct.save("dynamicMetrics.cct")
    cct.print()
