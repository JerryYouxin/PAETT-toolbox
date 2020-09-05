import numpy as np
import math
import os

import sys
from getopt import getopt

def make_core(core):
    if core<8:
        return 800000
    if core>22:
        return 2200000
    return core*100000

def make_uncore(uncore):
    if uncore<7:
        return 7*256+7
    if uncore>20:
        return 20*256+20
    return uncore*256+uncore

def read_data(benchmarks):
    res = {}
    for b in benchmarks:
        I_train = []
        O_train = []
        E_region= {}
        with open(b+"/metric.dat.search","r") as f:
            core=0
            uncore=0
            for line in f:
                cont = line.split(' ')
                if len(cont)==0:
                    continue
                if len(cont)==3 and cont[0]=='offset':
                    core=int(cont[1])
                    uncore=int(cont[2])
                else:
                    record = []
                    # print(line)
                    cont = line.split(';')
                    key = cont[0]
                    cont = cont[1].split(' ')
                    for s in cont:
                        record.append(float(s))
                    if key not in E_region.keys():
                        E_region[key] = ([],[],[]) # (thread, energy, metric)
                    E_region[key][0].append((core,uncore))
                    E_region[key][1].append(record[-1])
                    E_region[key][2].append(record[:-1])
        res[b] = (I_train, O_train, E_region)
    return res

def load_thread_cct(cct_fn, keymap_fn):
    keymap = {}
    with open(keymap_fn, "r") as f:
        for line in f:
            cont = line.split(" ")
            keymap[cont[0]] = " ".join(cont[1:])[:-1]
    cct = {}
    #cct["ROOT"] = [0, 0, 0, 0, {}]
    with open(cct_fn, "r") as f:
        for line in f:
            cont = line.split(" ")
            n = int(cont[0])
            #p = cct["ROOT"][4]
            p = cct
            for i in range(0, n):
                reg = keymap[cont[i+1]]
                if reg not in p.keys():
                    p[reg] = [0, 0, 0, None, {}]
                if i==n-1:
                    p[reg][0] = int(int(cont[n+1])/100000) # core
                    p[reg][1] = int(cont[n+2])&0xff # uncore
                    p[reg][2] = int(cont[n+3]) # thread
                p = p[reg][4]
    return cct

def print_cct(cct, pre=""):
    for reg in cct.keys():
        print(pre+"+ ",reg,cct[reg][:-1])
        print_cct(cct[reg][4], "|  "+pre)

def __prune_cct(cct):
    for reg in cct[4].keys():
        __prune_cct(cct[4][reg])
        valid=False
        for i in cct[4][reg][4].keys():
            valid = (valid or cct[4][reg][4][i][0]!=-1)
        # print(valid)
        if not valid:
            if cct[4][reg][0]==cct[0] and cct[4][reg][1]==cct[1] and cct[4][reg][2]==cct[2]:
                cct[4][reg][0]=-1

def __finetune_cct(cct):
    for reg in cct.keys():
        if cct[reg][3] is not None:
            index = np.argmin(cct[reg][3][1])
            coff, ucoff = cct[reg][3][0][index]
            # print(cct[reg][0],coff, cct[reg][1], ucoff)
            cct[reg][0] += coff
            cct[reg][1] += ucoff
        __finetune_cct(cct[reg][4])

def finetune_cct_with_data(cct, data):
    print_cct(cct)
    E_region = data[2]
    for key in E_region.keys():
        # index = np.argmin(E_region[key][1])
        # coff, ucoff = E_region[key][0][index]
        # now walk to the node in cct
        regions = key.split("=>")
        regions = regions[:-1]
        p = cct
        i = len(regions)-1
        # print("--------------------")
        # print(regions)
        while i>=0:
            # print(i, regions[i], p.keys())
            # print("->",i-1,regions[i-1], p[regions[i]][4].keys(), (regions[i-1] not in p[regions[i]][4].keys()))
            if (i==0) or (regions[i-1] not in p[regions[i]][4].keys()):
                if p[regions[i]][3] is None: 
                    p[regions[i]][3] = (E_region[key][0], E_region[key][1])
                else:
                    for j in range(0, len(p[regions[i]][3])):
                        p[regions[i]][3][1][j] += E_region[key][1][j]
                break
                # p[regions[i]][0]+= coff  # finetune core
                # p[regions[i]][1]+= ucoff # finetune uncore
                # # thread will not change
                # p[regions[i]][3] = E_region[key][1][index] # energy
            p = p[regions[i]][4] # switch to sub-tree
            i = i - 1
    __finetune_cct(cct)
    __prune_cct(cct["ROOT"])

def __finetune_cct_with_grandtruth(cct, grand_cct, sigList):
    for reg in cct.keys():
        if reg in grand_cct.keys():
            if grand_cct[reg][0]!=0 and grand_cct[reg][1]!=0 and (sigList==None or (reg in sigList)):
                print(reg, ":", cct[reg][:2], "=>", grand_cct[reg][:2])
                cct[reg][0] = grand_cct[reg][0]
                cct[reg][1] = grand_cct[reg][1]
            __finetune_cct_with_grandtruth(cct[reg][4], grand_cct[reg][4], sigList)

def merge_energy(cct):
    tot = 0.0
    E_region = data[2]
    for key in E_region.keys():
        tot += E_region[key][1][0]
    return tot

def finetune_cct_with_grandtruth(cct, grand_fn, grand_key_fn):
    grand_cct = load_thread_cct(grand_fn, grand_key_fn)
    # tot_energy= merge_energy(data)
    # sigList = [ "L:FourierTransform.C:704:3", "I:EnergyFunctional.C:1197:16", "L:EnergyFunctional.C:693:3" ]
    # sigList= [ "I:QuEST/src/CPU/QuEST_cpu.c:2095:1", "I:QuEST/src/CPU/QuEST_cpu.c:2855:1", "I:QuEST/src/CPU/QuEST_cpu.c:2573:1" ]
    sigList=None
    __finetune_cct_with_grandtruth(cct, grand_cct, sigList)

def __generate_cct_frequency_commands(f, cct, keyMap, coff=0, ucoff=0, pre=[]):
    for reg in cct.keys():
        if cct[reg][0]!=-1:
            key = len(keyMap.keys())
            if reg in keyMap.keys():
                key = keyMap[reg]
            else:
                keyMap[reg] = key
            f.write(str(len(pre)+1)+" ")
            for k in pre:
                f.write(str(k)+" ")
            f.write("{0} {1} {2} {3}\n".format(key, make_core(cct[reg][0]+coff), make_uncore(cct[reg][1]+ucoff), cct[reg][2]))
            # f.write("{0} {1} {2} {3}\n".format(key, make_core(22), make_uncore(20), 20))
            # children
            __generate_cct_frequency_commands(f, cct[reg][4], keyMap, coff, ucoff, pre+[key])

def generate_cct_frequency_commands(cct, name, enable_serach=False):
    keyMap = {}
    keyMap["ROOT"] = -1
    with open(name+".cct", "w", newline='') as f:
        # generate frequency commands first
        __generate_cct_frequency_commands(f, cct, keyMap)
    # generate frequency command filter for PAETT's compiler plugin
    with open(name+".filt","w", newline='') as f:
        for reg in keyMap.keys():
            f.write(str(keyMap[reg])+" ")
            f.write(reg+"\n")

def usage():
    return

if __name__=="__main__":
    data_src = ""
    keymap_fn = ""
    cct_src = ""
    out_fn = "frequency_command.finetune"
    opts, args = getopt(sys.argv[1:], "hp:k:c:o:", ["profile=","keymap=","cct-src=","output="])
    for opt, arg in opts:
        if opt=="-h":
            usage()
            sys.exit(1)
        elif opt in ("-p", "--profile"):
            data_src = arg
        elif opt in ("-k", "--keymap"):
            keymap_fn = arg
        elif opt in ("-c", "--cct-src"):
            cct_src = arg
        elif opt in ("-o", "--output"):
            out_fn = arg
    data = read_data([data_src])
    cct = load_thread_cct(cct_src, keymap_fn)
    # finetune_cct_with_grandtruth(cct, "frequency_command.cct", "frequency_command.filt")
    finetune_cct_with_data(cct, data[data_src])
    generate_cct_frequency_commands(cct, out_fn)