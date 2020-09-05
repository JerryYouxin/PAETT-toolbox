import numpy as np
import math
import os

from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import pickle

import sys
from getopt import getopt

def load(path):
    model = None
    with open(path, "rb") as f:
        model = pickle.load(f)
    return model

def read_data(benchmarks):
    res = {}
    for b in benchmarks:
        I_train = []
        O_train = []
        E_region= {}
        with open(b+"/metric.dat.thread","r") as f:
            thread=0
            for line in f:
                cont = line.split(' ')
                if len(cont)==0:
                    continue
                if len(cont)==2 and cont[0]=='Thread':
                    thread=int(cont[1])
                else:
                    assert(thread!=0)
                    record = []
                    # print(line)
                    cont = line.split(';')
                    key = cont[0]
                    cont = cont[1].split(' ')
                    for s in cont:
                        record.append(float(s))
                    if key not in E_region.keys():
                        E_region[key] = ([],[],[]) # (thread, energy, metric)
                    E_region[key][0].append(thread)
                    E_region[key][1].append(record[-1])
                    E_region[key][2].append(record[:-1])
        res[b] = (I_train, O_train, E_region)
    return res

def filter_data(data, test_num, energy_threshold):
    res = {}
    for b in data.keys():
        I_train = []
        O_train = []
        E_region_new = {}
        E_region= data[b][2]
        for key in E_region.keys():
            record = E_region[key]
            if len(record[1]) != test_num:
                # print("Remove region {0} as it has incorrect number of records ({1} data needed but has {2})".format(key, test_num, len(E_region[key][2])))
                key = "=>".join(key.split("=>")[1:])
            if max(record[1]) < energy_threshold:
                # print("Remove region {0} as it has too small energy values ({1} J, threshold={2} J)".format(key, min(E_region[key][2]), energy_threshold))
                # continue
                key = "=>".join(key.split("=>")[1:])
            # now use the maximum core/uncore's papi counter value as input (typically the last record)
            papi_val = record[2][-1][1:]
            if key not in E_region_new.keys():
                #E_region_new[key] = (record[0],record[1],[])
                E_region_new[key] = ([0 for i in range(0,test_num)], [0 for i in range(0,test_num)],[[0,0,0,0,0,0,0,0,0] for i in range(0, test_num)])
                for i in range(0,len(record[0])):
                    E_region_new[key][0][i] = record[0][i]
                    E_region_new[key][1][i] = record[1][i]
                    E_region_new[key][2][i] = [E_region_new[key][0][i]]+papi_val
            else:
                for i in range(0,len(record[0])):
                    E_region_new[key][1][i] += record[1][i]
                    for j in range(0,len(papi_val)):
                        E_region_new[key][2][i][j] += papi_val[j]
            I_train += E_region_new[key][2]
            O_train += E_region_new[key][1]
        print("{0}: Removed {1} regions containing dirty data, Remain {2} regions.".format(b,len(E_region.keys())-len(E_region_new.keys()), len(E_region_new.keys())))
        res[b] = (I_train, O_train, E_region_new)
    return res

def parse_data_to_cct(data, cct_fn, keymap_fn):
    cct = {}
    E_region = data[2]
    for key in E_region.keys():
        regions = key.split("=>")
        regions = regions[:-1]
        p = cct
        i = len(regions)-1
        while i>=0:
            if regions[i] not in p.keys():
                # core, uncore, thread, {"thread":(thread, metric, energy)}, subtree
                p[regions[i]] = [0, 0, 0, {}, {}, []]
            if i==0:
                #assert(p[regions[i]][0]==0)
                p[regions[i]][5] = E_region[key][1] # energy
                for j in range(0, len(E_region[key][0])):
                    kk = "{0}".format(E_region[key][0][j])
                    p[regions[i]][3][kk] = [ E_region[key][0][j], E_region[key][2][j], E_region[key][1][j] ]
            p = p[regions[i]][4] # switch to sub-tree
            i = i - 1
    return cct

def __filter_cct(cct_node, test_num, energy_threshold, name):
    filtered=False
    for key in cct_node[4].keys():
        filtered = filtered or __filter_cct(cct_node[4][key], test_num, energy_threshold, name+"=>"+key)
        #print(name+"=>"+key, len(cct_node[4][key][3].keys()), len(cct_node[4][key][5]))
        #if len(cct_node[4][key][5])>0:
            #print("-----", max(cct_node[4][key][5]), energy_threshold)
            #print( len(cct_node[4][key][3].keys()), test_num, (len(cct_node[4][key][3].keys()) != test_num) , (max(cct_node[4][key][5]) < energy_threshold))
        if (len(cct_node[4][key][3].keys()) != test_num) or (max(cct_node[4][key][5]) < energy_threshold):
            # merge data to parent
            for i in cct_node[4][key][3].keys():
                if i not in cct_node[3].keys():
                    cct_node[3][i] = cct_node[4][key][3][i]
                else:
                    cct_node[3][i][2] += cct_node[4][key][3][i][2]
                    for j in range(0, len(cct_node[4][key][3][i][1])):
                        cct_node[3][i][1][j] += cct_node[4][key][3][i][1][j]
            cct_node[5] = []
            for i in cct_node[3]:
                cct_node[5].append(cct_node[3][i][2])
            if len(cct_node[4][key][3].keys())!=0:
                filtered = True
                print("Filtered", key)
            # clear this child's data
            cct_node[4][key][3] = {}
    return filtered

def filter_cct(cct, test_num, energy_threshold):
    while __filter_cct(cct["ROOT"], test_num, energy_threshold, "ROOT"):
        pass
    
def getOptFreq4CCT(cct, thread_fix, model=None):
    for key in cct.keys():
        getOptFreq4CCT(cct[key][4], thread_fix, model)
        energy_all = []
        thread_all   = []
        metric_all = []
        # print(len(cct[key][3].keys()))
        for c in cct[key][3].keys():
            energy_all.append(cct[key][3][c][2])
            thread_all.append(cct[key][3][c][0])
            metric_all.append(cct[key][3][c][1])
        if len(energy_all)>0:
            if thread_fix==0:
                index = np.argmin(energy_all)
                cct[key][2] = thread_all[index]
            else:
                cct[key][2] = thread_fix
                for i in range(0, len(thread_all)):
                    if thread_all[i]==thread_fix:
                        index = i
                        break
            if model is not None:
                inp = []
                for c in range(8,23):
                    for uc in range(7,21):
                        inp.append([c, uc]+metric_all[index])
                pred = model.predict(np.array(inp))
                # print(inp)
                # print(pred)
                j = np.argmin(pred)
                cct[key][0] = inp[j][0]
                cct[key][1] = inp[j][1]

'''
def filter_data(data, test_num, energy_threshold):
    res = {}
    for b in data.keys():
        I_train = []
        O_train = []
        E_region_new = {}
        E_region= data[b][2]
        for key in E_region.keys():
            if len(E_region[key][1]) != test_num:
                # print("Remove region {0} as it has incorrect number of records ({1} data needed but has {2})".format(key, test_num, len(E_region[key][2])))
                continue
            if max(E_region[key][1]) < energy_threshold:
            #     # print("Remove region {0} as it has too small energy values ({1} J, threshold={2} J)".format(key, min(E_region[key][2]), energy_threshold))
                continue
            # now use the maximum core/uncore's papi counter value as input (typically the last record)
            E_region_new[key] = (E_region[key][0],E_region[key][1], E_region[key][2])
        print("{0}: Removed {1} regions containing dirty data, Remain {2} regions.".format(b,len(E_region.keys())-len(E_region_new.keys()), len(E_region_new.keys())))
        res[b] = (I_train, O_train, E_region_new)
    return res
'''
def getStaticalRegionData(data):
    res = {}
    E_region = data[2]
    for key in E_region.keys():
        reg = key.split("=>")[0]
        if reg not in res.keys():
            res[reg] = {}
            res[reg][reg] = (E_region[key][0],E_region[key][1]) # (thread, energy)
        else:
            for i in range(0, len(E_region[key][0])):
                res[reg][reg][1][i] += E_region[key][1][i]
        if key not in res[reg].keys():
            res[reg][key] = (E_region[key][0],E_region[key][1])
    return res

def getStaticFreqOfMinEnergy(data):
    comb_list = []
    E = []
    E_region = data[2]
    for key in E_region.keys():
        for i in range(0, len(E_region[key][1])):
            thread= E_region[key][0][i]
            energy= E_region[key][1][i]
            comb = (thread)
            if thread<=0 or energy<=0:
                continue
            found = False
            for c in range(0,len(comb_list)):
                if comb_list[c]==comb:
                    E[c] += energy
                    found = True
                    break
            if not found:
                comb_list.append(comb)
                E.append(energy)
    index = np.argmin(E)
    return comb_list[index], E[index]

def getFreqOfMinEnergy(data):
    res = {}
    E_region = data[2]
    for key in E_region.keys():
        index = np.argmin(E_region[key][1])
        # index = len(E_region[key][1])-1
        thread = E_region[key][0][index]
        energy = E_region[key][1][index]
        metric = E_region[key][2][index]
        res[key] = (thread, energy, metric)
    return res

def getFreqOfMinEnergyRegion(data):
    res = {}
    reg2cct = {}
    E_region = data[2]
    E_region_new = {}
    for key in E_region.keys():
        reg = key.split("=>")[0]
        if reg not in E_region_new.keys():
            E_region_new[reg] = (E_region[key][0],E_region[key][1]) # (thread, energy)
            reg2cct[reg] = [key]
        else:
            for i in range(0, len(E_region[key][0])):
                E_region_new[reg][1][i] += E_region[key][1][i]
            reg2cct[reg].append(key)
    for reg in E_region_new.keys():
        index = np.argmin(E_region_new[reg][1])
        thread= E_region_new[reg][0][index]
        energy= E_region_new[reg][1][index]
        res[reg] = (thread, energy)
    return res, reg2cct
    
def make_core(core):
    if core==0:
        return 0
    if core<8:
        return 800000
    if core>22:
        return 2200000
    return core*100000

def make_uncore(uncore):
    if uncore==0:
        return 0
    if uncore<7:
        return 7*256+7
    if uncore>20:
        return 20*256+20
    return uncore*256+uncore

def generate_frequency_commands(data, file_name):
    with open(file_name, "w") as f:
        f.write("1 ")
        for key in data.keys():
            f.write("{0} {1};{2} {3} {4} {5} {6} {7}\n".format(0, key, 0, 0, data[key][0], 0, 0, 0))

def parse_cctString_to_cct(data, model=None):
    res = {} # "region":(thread, energy, {...})
    for key in data.keys():
        regions = key.split("=>")
        regions = regions[:-1]
        input_data = []
        if model is not None:
            for c in range(8, 23):
                for uc in range(7,21):
                    input_data.append([c, uc]+data[key][2])
            #print(key)
            #print(input_data)
        p = res
        i = len(regions)-1
        while i>=0:
            if regions[i] not in p.keys():
                p[regions[i]] = [0, 0, 0, 0, {}] # core, uncore, thread, energy, sub-tree
            if i==0:
                assert(p[regions[i]][0]==0)
                if model is not None:
                    pred = model.predict(np.array(input_data))
                    index = pred.argmin()
                    #print(pred)
                    #print(index)
                    p[regions[i]][0] = input_data[index][0] # core
                    p[regions[i]][1] = input_data[index][1] # uncore
                p[regions[i]][2] = data[key][0] # thread
                p[regions[i]][3] = data[key][1] # energy
            p = p[regions[i]][4] # switch to sub-tree
            i = i - 1
    return res

def __optimize_cct(cct):
    for reg in cct.keys():
        __optimize_cct(cct[reg][4])
        core=cct[reg][0]
        uncore=cct[reg][1]
        thread=cct[reg][2]
        for r in cct[reg][4].keys():
            if core!=0 and core!=cct[reg][4][r][0]:
                core = -1
            if core==0:
                core = cct[reg][4][r][0]
            if uncore!=0 and uncore!=cct[reg][4][r][1]:
                uncore = -1
            if uncore==0:
                uncore = cct[reg][4][r][1]
            if thread!=0 and thread!=cct[reg][4][r][2]:
                thread = -1
            if thread==0:
                thread = cct[reg][4][r][2]
        if core>0:
            cct[reg][0] = core
        if uncore>0:
            cct[reg][1] = uncore
        if thread>0:
            cct[reg][2] = thread

def __prune_cct(cct_node):
    valid= (cct_node[0]>0 or cct_node[1]>0 or cct_node[2]>0)
    for reg in cct_node[4].keys():
        valid = __prune_cct(cct_node[4][reg]) or valid
        if cct_node[4][reg][0]>0 or cct_node[4][reg][1]>0 or cct_node[4][reg][2]>0:
            valid = True
    if not valid:
        cct_node[0] = -1
    print("Pruning {0}: {1}".format(cct_node[:3], not valid))
    return valid
    # for reg in cct[4].keys():
    #     __prune_cct(cct[4][reg])
    #     valid=False
    #     for i in cct[4][reg][4].keys():
    #         valid = (valid or cct[4][reg][4][i][0]!=-1)
    #     print(valid)
    #     if not valid:
    #         if cct[4][reg][0]==cct[0] and cct[4][reg][1]==cct[1] and cct[4][reg][2]==cct[2]:
    #             cct[4][reg][0]=-1

def optimize_cct(cct, prune):
    __optimize_cct(cct["ROOT"][4])
    core=0
    uncore=0
    thread=0
    for r in cct["ROOT"][4].keys():
        if core!=0 and core!=cct["ROOT"][4][r][0]:
            core = -1
        if core==0:
            core = cct["ROOT"][4][r][0]
        if uncore!=0 and uncore!=cct["ROOT"][4][r][1]:
            uncore = -1
        if uncore==0:
            uncore = cct["ROOT"][4][r][1]
        if thread!=0 and thread!=cct["ROOT"][4][r][2]:
            thread = -1
        if thread==0:
            thread = cct["ROOT"][4][r][2]
    if core>0:
        cct["ROOT"][0] = core
    if uncore>0:
        cct["ROOT"][1] = uncore
    if thread>0:
        cct["ROOT"][2] = thread
    if prune:
        __prune_cct(cct["ROOT"])
    print_cct(cct)

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
            # children
            __generate_cct_frequency_commands(f, cct[reg][4], keyMap, coff, ucoff, pre+[key])

def generate_cct_frequency_commands(cct, name, enable_serach=False):
    keyMap = {}
    keyMap["ROOT"] = -1
    with open(name+".cct", "w", newline='') as f:
        # generate frequency commands first
        __generate_cct_frequency_commands(f, cct, keyMap)
    if enable_serach:
        for c in [-2,-1,0,1,2]:
            for uc in [-2,-1,0,1,2]:
                with open(name+".cct."+str(c)+"."+str(uc), "w", newline='') as f:
                    __generate_cct_frequency_commands(f, cct, keyMap, c, uc)
        # with open(name+".cct.cp1", "w", newline='') as f:
        #     # generate frequency commands first
        #     __generate_cct_frequency_commands(f, cct, keyMap,1,0)
        # with open(name+".cct.up1", "w", newline='') as f:
        #     # generate frequency commands first
        #     __generate_cct_frequency_commands(f, cct, keyMap,0,1)
        # with open(name+".cct.cm1", "w", newline='') as f:
        #     # generate frequency commands first
        #     __generate_cct_frequency_commands(f, cct, keyMap,-1,0)
        # with open(name+".cct.um1", "w", newline='') as f:
        #     # generate frequency commands first
        #     __generate_cct_frequency_commands(f, cct, keyMap,0,-1)
    # generate frequency command filter for PAETT's compiler plugin
    with open(name+".filt","w", newline='') as f:
        for reg in keyMap.keys():
            f.write(str(keyMap[reg])+" ")
            f.write(reg+"\n")

def print_cct(cct, pre=""):
    for reg in cct.keys():
        print(pre+"+ ",reg,cct[reg][:3])
        print_cct(cct[reg][4], "|  "+pre)

# def parse_cct_to_insert_point(data):
#     res = {}
#     for key in data.keys():
#         regions = key.split("=>")
#         regions = regions[:-1] # delete the last one (it is always empty)
#         fail=True
#         for reg in regions:
#             check = True
#             for comp in data.keys():
#                 if comp!=key and ((reg+"=>") in comp):
#                     check = False
#                     break
#             if check:
#                 fail=False
#                 res[reg] = data[key]
#                 break
#         if fail:
#             print("Failed to get insert point for key ", key)
#     return res

def usage():
    return

if __name__=="__main__":
    MODEL_PATH=None
    model=None
    BENCH="QBOX/"
    thread_fix=0
    #BENCH="streamcluster/"
    data_src = "./data/"+BENCH
    opts, args = getopt(sys.argv[1:], "hp:m:t:", ["profile=","model=","thread="])
    for opt, arg in opts:
        if opt=="-h":
            usage()
            sys.exit(1)
        elif opt in ("-p", "--profile"):
            data_src = arg
        elif opt in ("-m", "--model"):
            MODEL_PATH = arg
        elif opt in ("-t", "--thread"):
            thread_fix = int(arg)
    if MODEL_PATH is not None:
        model = load(MODEL_PATH)
    print("Reading Data...")
    data = read_data([data_src])

    cct = parse_data_to_cct(data[data_src], "frequency_command.thread.cct", "frequency_command.thread.filt")
    filter_cct(cct, 11, 40)
    #filter_cct(cct, 9, 40)
    #filter_cct(cct, 1, 40)
    getOptFreq4CCT(cct, thread_fix, model)
    #optimize_cct(cct, False)
    optimize_cct(cct, True)
    generate_cct_frequency_commands(cct, data_src+"frequency_command.thread", model is not None)

    # print("Filter dirty data...")
    #data = filter_data(data, 11, 5)
    data = filter_data(data, 9, 5)
    # data = filter_data(data, (20-7+1)+(14-7+1)+1, 20)
    FreqOfMinEnergy = getFreqOfMinEnergy(data[data_src])
    FreqOfMinEnergyRegion, reg2cct = getFreqOfMinEnergyRegion(data[data_src])
    freq, Emin = getStaticFreqOfMinEnergy(data[data_src])
    print("Static Minimal: ",freq, Emin)
    for reg in reg2cct.keys():
        if len(reg2cct[reg])>1:
            print(reg, FreqOfMinEnergyRegion[reg])
            tot_energy = 0
            cct_list = reg2cct[reg]
            for cct in cct_list:
                print("\t",cct, "\n\t  ", FreqOfMinEnergy[cct][:-1])
                tot_energy += FreqOfMinEnergy[cct][1]
            print("\tCCT-based Energy=",tot_energy, "J, Region-based Energy=", FreqOfMinEnergyRegion[reg][1],"J, Saving ", 100*(1-tot_energy/FreqOfMinEnergyRegion[reg][1]), "%")
    # cct = parse_cctString_to_cct(FreqOfMinEnergy, model)
    # print_cct(cct)
    # #optimize_cct(cct, model is not None)
    # optimize_cct(cct, False)
    # generate_cct_frequency_commands(cct, data_src+"frequency_command.thread", model is not None)
    # generate_frequency_commands(FreqOfMinEnergyRegion, data_src+"paett_model.cache.thread.region")
