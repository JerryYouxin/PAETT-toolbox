import numpy as np
import math
import os
#'''
import matplotlib
import matplotlib.pyplot as plt
import os

import matplotlib.patches as patches
#'''

def heatmap(data, row_labels, col_labels, ax=None,
            cbar_kw={}, cbarlabel="", **kwargs):
    """
    Create a heatmap from a numpy array and two lists of labels.

    Parameters
    ----------
    data
        A 2D numpy array of shape (N, M).
    row_labels
        A list or array of length N with the labels for the rows.
    col_labels
        A list or array of length M with the labels for the columns.
    ax
        A `matplotlib.axes.Axes` instance to which the heatmap is plotted.  If
        not provided, use current axes or create a new one.  Optional.
    cbar_kw
        A dictionary with arguments to `matplotlib.Figure.colorbar`.  Optional.
    cbarlabel
        The label for the colorbar.  Optional.
    **kwargs
        All other arguments are forwarded to `imshow`.
    """

    if not ax:
        ax = plt.gca()

    # Plot the heatmap
    im = ax.imshow(data, **kwargs)

    # Create colorbar
    cbar = ax.figure.colorbar(im, ax=ax, **cbar_kw)
    cbar.ax.set_ylabel(cbarlabel, rotation=-90, va="bottom")

    # We want to show all ticks...
    ax.set_xticks(np.arange(data.shape[1]))
    ax.set_yticks(np.arange(data.shape[0]))
    # ... and label them with the respective list entries.
    ax.set_xticklabels(col_labels)
    ax.set_yticklabels(row_labels)

    # Let the horizontal axes labeling appear on top.
    ax.tick_params(top=False, bottom=True,
                   labeltop=False, labelbottom=True)

    # Rotate the tick labels and set their alignment.
    # plt.setp(ax.get_xticklabels(), rotation=-30, ha="right",
    #          rotation_mode="anchor")

    # Turn spines off and create white grid.
    for edge, spine in ax.spines.items():
        spine.set_visible(False)

    ax.set_xticks(np.arange(data.shape[1]+1)-.5, minor=True)
    ax.set_yticks(np.arange(data.shape[0]+1)-.5, minor=True)
    ax.set_xlabel("Uncore Frequency (GHz)")
    ax.set_ylabel("Core Frequency (GHz)")
    ax.grid(which="minor", color="w", linestyle='-', linewidth=3)
    ax.tick_params(which="minor", bottom=False, left=False)

    return im, cbar


def annotate_heatmap(im, data=None, valfmt="{x:.2f}",
                     textcolors=["black", "white"],
                     threshold=None, **textkw):
    """
    A function to annotate a heatmap.

    Parameters
    ----------
    im
        The AxesImage to be labeled.
    data
        Data used to annotate.  If None, the image's data is used.  Optional.
    valfmt
        The format of the annotations inside the heatmap.  This should either
        use the string format method, e.g. "$ {x:.2f}", or be a
        `matplotlib.ticker.Formatter`.  Optional.
    textcolors
        A list or array of two color specifications.  The first is used for
        values below a threshold, the second for those above.  Optional.
    threshold
        Value in data units according to which the colors from textcolors are
        applied.  If None (the default) uses the middle of the colormap as
        separation.  Optional.
    **kwargs
        All other arguments are forwarded to each call to `text` used to create
        the text labels.
    """

    if not isinstance(data, (list, np.ndarray)):
        data = im.get_array()

    # Normalize the threshold to the images color range.
    if threshold is not None:
        threshold = im.norm(threshold)
    else:
        threshold = im.norm(data.max())/2.

    # Set default alignment to center, but allow it to be
    # overwritten by textkw.
    kw = dict(horizontalalignment="center",
              verticalalignment="center")
    kw.update(textkw)

    # Get the formatter in case a string is supplied
    if isinstance(valfmt, str):
        valfmt = matplotlib.ticker.StrMethodFormatter(valfmt)

    # Loop over the data and create a `Text` for each "pixel".
    # Change the text's color depending on the data.
    texts = []
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            kw.update(color=textcolors[int(im.norm(data[i, j]) > threshold)])
            text = im.axes.text(j, i, valfmt(data[i, j], None), **kw)
            texts.append(text)

    return texts

def add_rect(c,u, color, zorder=10):
    plt.gca().add_patch(plt.Rectangle((u-0.5, c-0.5),1,1,linewidth=2.5,edgecolor=color,facecolor='none',zorder=zorder))

def draw(log_data, c_prec=0, u_prec=0, title="", pre=""):
    emin = 99999
    cm = 0
    ucm = 0
    # 8-22,7-20 (15x14)
    heatmaps = [ [ 0 for j in range(0,14) ] for i in range(0,15) ]
    for i in range(0, len(log_data[0])):
        core = log_data[0][i]
        uncore = log_data[1][i]
        energy = log_data[2][i]
        # print(core, uncore, energy)
        heatmaps[int(core)-8][int(uncore)-7] = energy
    # normalize to 22/20
    for c in range(0,15):
        for uc in range(0,14):
            heatmaps[c][uc] /= heatmaps[14][13]
    clist = []
    ulist = []
    delta = 0.05
    for c in range(0,15):
        for uc in range(0,14):
            if emin > heatmaps[c][uc] and heatmaps[c][uc]!=0:
                emin = heatmaps[c][uc]
                cm = c
                ucm = uc
    for c in range(0,15):
        for uc in range(0,14):
            if abs(heatmaps[c][uc]-emin) <= delta:
                clist.append(c)
                ulist.append(uc)
    # print(cm, ucm)
    # print(clist, ulist)
    # ============================================ #
    fig, ax2 = plt.subplots()

    heatmap_val = np.array(heatmaps)
    X_CF = [ (8+i)/10.0 for i in range(0,15) ]
    Y_UCF= [ (7+i)/10.0 for i in range(0,14) ]
    
    im, cbar = heatmap(heatmap_val, X_CF, Y_UCF, ax=ax2,
                   cmap="YlGn", cbarlabel="Normalized CPU Package Energy")
    texts = annotate_heatmap(im, valfmt="{x:.2f}")

    fig.tight_layout()
    fig.set_size_inches(11,8)
    add_rect(cm, ucm, 'r', 10)
    for i in range(len(clist)):
        if clist[i]!=cm or ulist[i]!=ucm:
            add_rect(clist[i],ulist[i], 'yellow', 8)
    if c_prec>=8 and u_prec>=7:
        add_rect(c_prec-8, u_prec-7, 'orange', 9)
    # if the prec core/uncore energy is different from the minimum energy for more than 3%, add a tag
    if heatmaps[c_prec-8][u_prec-7] - emin > 0.03:
        print(pre)
        pre += "#"
    # ax2.set_title(title)
    plt.savefig(pre+"heatmap.pdf", bbox_inches = 'tight')
    # plt.show()
    plt.close()

def read_data(benchmarks):
    res = {}
    for b in benchmarks:
        I_train = []
        O_train = []
        E_region= {}
        with open(b+"/metric.dat.3","r") as f:
            core=0
            uncore=0
            for line in f:
                cont = line.split(' ')
                if len(cont)==0:
                    continue
                if len(cont)==3 and cont[0]=='Freq':
                    core=int(cont[1])
                    uncore=int(cont[2])
                else:
                    assert(core!=0 and uncore!=0)
                    record = [core, uncore]
                    # print(line)
                    cont = line.split(';')
                    key = cont[0]
                    if key not in E_region.keys():
                        E_region[key] = ([],[],[],[]) # (core, uncore, energy, model_input)
                    cont = cont[1].split(' ')
                    for s in cont:
                        record.append(float(s))
                    I_train.append(record[:-1])
                    O_train.append(record[-1])
                    E_region[key][0].append(core)
                    E_region[key][1].append(uncore)
                    E_region[key][2].append(record[-1])
                    E_region[key][3].append(record[:-1])
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
            if len(record[2]) != test_num:
                # print("Remove region {0} as it has incorrect number of records ({1} data needed but has {2})".format(key, test_num, len(E_region[key][2])))
                # continue
                key = "=>".join(key.split("=>")[1:])
            if max(record[2]) < energy_threshold:
                # print("Remove region {0} as it has too small energy values ({1} J, threshold={2} J)".format(key, min(E_region[key][2]), energy_threshold))
                # continue
                key = "=>".join(key.split("=>")[1:])
            # now use the maximum core/uncore's papi counter value as input (typically the last record)
            papi_val = record[3][-1][2:]
            if key not in E_region_new.keys():
                #E_region_new[key] = (record[0],record[1],record[2],[])
                E_region_new[key] = ([0 for i in range(0,test_num)], [0 for i in range(0,test_num)], [0 for i in range(0,test_num)],[[0,0,0,0,0,0,0,0,0] for i in range(0, test_num)])
                for i in range(0,len(record[0])):
                    E_region_new[key][0][i] = record[0][i]
                    E_region_new[key][1][i] = record[1][i]
                    E_region_new[key][2][i] = record[2][i]
                    #E_region_new[key][3].append([E_region_new[key][0][i], E_region_new[key][1][i]]+papi_val)
                    E_region_new[key][3][i] = [E_region_new[key][0][i], E_region_new[key][1][i]]+papi_val
            else:
                for i in range(0,len(record[0])):
                    E_region_new[key][0][i] = record[0][i]
                    E_region_new[key][1][i] = record[1][i]
                    E_region_new[key][2][i] += record[2][i]
                    for j in range(0,len(papi_val)):
                        E_region_new[key][3][i][j] += papi_val[j]
            I_train += E_region_new[key][3]
            O_train += E_region_new[key][2]
        print("{0}: Removed {1} regions containing dirty data, Remain {2} regions.".format(b,len(E_region.keys())-len(E_region_new.keys()), len(E_region_new.keys())))
        res[b] = (I_train, O_train, E_region_new)
    return res

def __load_thread_cct_v2(cct_fn, keymap_fn):
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
                    p[reg] = [0, 0, 0, {}, {}, []]
                if i==n-1:
                    p[reg][0] = int(0) # core
                    p[reg][1] = int(0) # uncore
                    p[reg][2] = int(cont[n+3]) # thread
                p = p[reg][4]
    return cct

def parse_data_to_cct(data, cct_fn, keymap_fn):
    cct = __load_thread_cct_v2(cct_fn, keymap_fn)
    E_region = data[2]
    for key in E_region.keys():
        regions = key.split("=>")
        regions = regions[:-1]
        p = cct
        i = len(regions)-1
        while i>=0:
            if regions[i] not in p.keys():
                # core, uncore, thread, {"core uncore":(core, uncore, metric, energy)}, subtree
                p[regions[i]] = [0, 0, 0, {}, {}, []]
            if i==0:
                #assert(p[regions[i]][0]==0)
                # p[regions[i]][0] = E_region[key][0] # core
                # p[regions[i]][1] = E_region[key][1] # uncore
                p[regions[i]][5] = E_region[key][2] # energy
                for j in range(0, len(E_region[key][0])):
                    kk = "{0} {1}".format(E_region[key][0][j], E_region[key][1][j])
                    p[regions[i]][3][kk] = [ E_region[key][0][j], E_region[key][1][j], E_region[key][3][j], E_region[key][2][j] ]
                    print(kk, p[regions[i]][3][kk])
            p = p[regions[i]][4] # switch to sub-tree
            i = i - 1
    return cct

def __filter_cct(cct_node, test_num, energy_threshold, name):
    filtered=False
    for key in cct_node[4].keys():
        filtered = filtered or __filter_cct(cct_node[4][key], test_num, energy_threshold, name+"=>"+key)
        print(name+"=>"+key, len(cct_node[4][key][3].keys()), len(cct_node[4][key][5]))
        if (len(cct_node[4][key][3].keys()) != test_num) or (max(cct_node[4][key][5]) < energy_threshold):
            # merge data to parent
            for i in cct_node[4][key][3].keys():
                if i not in cct_node[3].keys():
                    cct_node[3][i] = cct_node[4][key][3][i]
                else:
                    cct_node[3][i][3] += cct_node[4][key][3][i][3]
                    for j in range(0, len(cct_node[4][key][3][i][2])):
                        cct_node[3][i][2][j] += cct_node[4][key][3][i][2][j]
            cct_node[5] = []
            for i in cct_node[3]:
                cct_node[5].append(cct_node[3][i][3])
            if len(cct_node[4][key][3].keys())!=0:
                filtered = True
                print("Filtered", key)
            # clear this child's data
            cct_node[4][key][3] = {}
    return filtered

def filter_cct(cct, test_num, energy_threshold):
    while __filter_cct(cct["ROOT"], test_num, energy_threshold, "ROOT"):
        pass
    
def getOptFreq4CCT(cct):
    for key in cct.keys():
        getOptFreq4CCT(cct[key][4])
        energy_all = []
        core_all   = []
        uncore_all = []
        print(len(cct[key][3].keys()))
        for c in cct[key][3].keys():
            energy_all.append(cct[key][3][c][3])
            core_all.append(cct[key][3][c][0])
            uncore_all.append(cct[key][3][c][1])
        if len(energy_all)>0:
            index = np.argmin(energy_all)
            cct[key][0] = core_all[index]
            cct[key][1] = uncore_all[index]

def getStaticalRegionData(data):
    res = {}
    E_region = data[2]
    for key in E_region.keys():
        if len(E_region[key][2]) != (22-8+1)*(20-7+1):
                # print("Remove region {0} as it has incorrect number of records ({1} data needed but has {2})".format(key, test_num, len(E_region[key][2])))
                continue
        if min(E_region[key][2]) < 1:
            # print("Remove region {0} as it has too small energy values ({1} J, threshold={2} J)".format(key, min(E_region[key][2]), energy_threshold))
            continue
        reg = key.split("=>")[0]
        if reg not in res.keys():
            res[reg] = {}
            res[reg][reg] = (E_region[key][0],E_region[key][1],E_region[key][2]) # (core, uncore, energy)
        else:
            for i in range(0, len(E_region[key][0])):
                res[reg][reg][2][i] += E_region[key][2][i]
        if key not in res[reg].keys():
            res[reg][key] = (E_region[key][0],E_region[key][1],E_region[key][2])
    return res

def getStaticFreqOfMinEnergy(data):
    comb_list = []
    E = []
    E_region = data[2]
    for key in E_region.keys():
        for i in range(0, len(E_region[key][2])):
            core = E_region[key][0][i]
            uncore= E_region[key][1][i]
            energy= E_region[key][2][i]
            comb = (core, uncore)
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
        index = np.argmin(E_region[key][2])
        core = E_region[key][0][index]
        uncore= E_region[key][1][index]
        energy= E_region[key][2][index]
        res[key] = (core, uncore, energy, E_region[key][3][index])
    return res

def getFreqOfMinEnergyRegion(data):
    res = {}
    reg2cct = {}
    E_region = data[2]
    E_region_new = {}
    E = 0
    for key in E_region.keys():
        E += E_region[key][2][-1]
        reg = key.split("=>")[0]
        if reg not in E_region_new.keys():
            E_region_new[reg] = (E_region[key][0],E_region[key][1],E_region[key][2]) # (core, uncore, energy)
            reg2cct[reg] = [key]
        else:
            for i in range(0, len(E_region[key][0])):
                E_region_new[reg][2][i] += E_region[key][2][i]
            reg2cct[reg].append(key)
    for reg in E_region_new.keys():
        index = np.argmin(E_region_new[reg][2])
        core = E_region_new[reg][0][index]
        uncore= E_region_new[reg][1][index]
        energy= E_region_new[reg][2][index]
        res[reg] = (core, uncore, E_region_new[reg][2][-1])
        print("{0}:\t{1} J ({2} J),\trate={3}%".format(reg, energy, E,energy/E*100))
    return res, reg2cct
    
def make_core(core):
    return core*100000

def make_uncore(uncore):
    return uncore*256+uncore

def generate_frequency_commands(data, file_name):
    with open(file_name, "w") as f:
        f.write("1 ")
        for key in data.keys():
            f.write("{0} {1};{2} {3} {4} {5} {6} {7}\n".format(0, key, data[key][0]*100000, data[key][1]*256+data[key][1], 0, make_core(22),make_uncore(20),0))

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
                    p[reg] = [0, 0, 0, 0, {}]
                if i==n-1:
                    #p[reg][0] = int(cont[n+1]) # core
                    #p[reg][1] = int(cont[n+2]) # uncore
                    p[reg][0] = int(0) # core
                    p[reg][1] = int(0) # uncore
                    p[reg][3] = int(cont[n+3]) # thread
                p = p[reg][4]
    return cct

def parse_cctString_to_cct(data, cct_init={}):
    res = cct_init # "region":(core, uncore, energy, thread, {...})
    for key in data.keys():
        regions = key.split("=>")
        regions = regions[:-1]
        p = res
        i = len(regions)-1
        while i>=0:
            if regions[i] not in p.keys():
                p[regions[i]] = [0, 0, 0, 0, {}]
            if i==0:
                #assert(p[regions[i]][0]==0)
                p[regions[i]][0] = data[key][0]
                p[regions[i]][1] = data[key][1]
                p[regions[i]][2] = data[key][2]
            p = p[regions[i]][4]
            i = i - 1
    return res

def __optimize_cct(cct):
    for reg in cct.keys():
        __optimize_cct(cct[reg][4])
        core=0
        uncore=0
        for r in cct[reg][4].keys():
            if core!=0 and core!=cct[reg][4][r][0]:
                core = 0
                break
            if uncore!=0 and uncore!=cct[reg][4][r][1]:
                uncore = 0
                break
            core = cct[reg][4][r][0]
            uncore = cct[reg][4][r][1]
        if core!=0 and uncore!=0:
            cct[reg][0] = core
            cct[reg][1] = uncore

def __prune_cct(cct):
    for reg in cct[4].keys():
        __prune_cct(cct[4][reg])
        valid=False
        for i in cct[4][reg][4].keys():
            valid = (valid or cct[4][reg][4][i][0]!=-1)
        print(valid)
        if not valid:
            if (cct[4][reg][0]==cct[0] or cct[4][reg][0]==0) and (cct[4][reg][1]==cct[1] or cct[4][reg][1]==0) and (cct[4][reg][3]==cct[3] or cct[4][reg][3]==0):
                cct[4][reg][0]=-1

def optimize_cct(cct):
    __optimize_cct(cct["ROOT"][4])
    core=0
    uncore=0
    for r in cct["ROOT"][4].keys():
        if core!=0 and core!=cct["ROOT"][4][r][0]:
            core = 0
            break
        if uncore!=0 and uncore!=cct["ROOT"][4][r][1]:
            uncore = 0
            break
        core = cct["ROOT"][4][r][0]
        uncore = cct["ROOT"][4][r][1]
    if core!=0 and uncore!=0:
        cct["ROOT"][0] = core
        cct["ROOT"][1] = uncore
    __prune_cct(cct["ROOT"])
    print_cct(cct)

def __generate_cct_frequency_commands(f, cct, keyMap, pre=[]):
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
            # f.write("{0} {1} {2} {3}\n".format(key, make_core(cct[reg][0]), make_uncore(cct[reg][1]), cct[reg][3]))
            f.write("{0} {1} {2} {3}\n".format(key, make_core(cct[reg][0]), make_uncore(cct[reg][1]), cct[reg][2]))
            # children
            __generate_cct_frequency_commands(f, cct[reg][4], keyMap, pre+[key])

def generate_cct_frequency_commands(cct, name):
    keyMap = {}
    keyMap["ROOT"] = -1
    with open(name+".cct", "w", newline='') as f:
        # generate frequency commands first
        #__generate_cct_frequency_commands(f, cct["ROOT"][4], keyMap)
        __generate_cct_frequency_commands(f, cct, keyMap)
    # generate frequency command filter for PAETT's compiler plugin
    with open(name+".filt","w", newline='') as f:
        for reg in keyMap.keys():
            f.write(str(keyMap[reg])+" ")
            f.write(reg+"\n")

def print_cct(cct, pre=""):
    for reg in cct.keys():
        print(pre+"+ ",reg,cct[reg][:3])
        print_cct(cct[reg][4], "|  "+pre)

def parse_cct_to_insert_point(data):
    res = {}
    for key in data.keys():
        regions = key.split("=>")
        regions = regions[:-1] # delete the last one (it is always empty)
        fail=True
        for reg in regions:
            check = True
            for comp in data.keys():
                if comp!=key and ((reg+"=>") in comp):
                    check = False
                    break
            if check:
                fail=False
                res[reg] = data[key]
                break
        if fail:
            print("Failed to get insert point for key ", key)
    return res

if __name__=="__main__":
    # BENCH="streamcluster/"
    #BENCH="QBOX/"
    BENCH="miniMD/"
    data_src = "./data/"+BENCH
    #data_src = "./"
    print("Reading Data...")
    data = read_data([data_src])
    print("Filter dirty data...")
    # cct = parse_data_to_cct(data[data_src], "frequency_command.thread.cct", "frequency_command.thread.filt")
    # filter_cct(cct, (22-8+1)*(20-7+1), 10)
    # # print_cct(cct)
    # getOptFreq4CCT(cct)
    # print_cct(cct)
    # print_cct(cct)
    # optimize_cct(cct)
    # generate_cct_frequency_commands(cct, data_src+"frequency_command")
    data = filter_data(data, (22-8+1)*(20-7+1), 10)
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
                print("\t",cct, "\n\t  ", FreqOfMinEnergy[cct])
                tot_energy += FreqOfMinEnergy[cct][2]
            print("\tCCT-based Energy=",tot_energy, "J, Region-based Energy=", FreqOfMinEnergyRegion[reg][2],"J, Saving ", 100*(1-tot_energy/FreqOfMinEnergyRegion[reg][2]), "%")
    # cct = load_thread_cct(data_src+"PAETT-profile/frequency_command.thread.cct", data_src+"PAETT-profile/frequency_command.thread.filt")
    # #cct = {}
    # cct = parse_cctString_to_cct(FreqOfMinEnergy, cct)
    # print_cct(cct)
    # optimize_cct(cct)
    # generate_cct_frequency_commands(cct, data_src+"frequency_command")
    generate_frequency_commands(FreqOfMinEnergyRegion, data_src+"paett_model.cache.region")
    generate_frequency_commands(parse_cct_to_insert_point(FreqOfMinEnergy), data_src+"paett_model.cache.cct")
    # # generate heatmap figures for further analysis
    regData = getStaticalRegionData(data[data_src])
    for reg in regData.keys():
        path = "./figures/"+BENCH+reg.replace("/",";").replace(":","#")
        try:
            os.mkdir(path)
        except FileExistsError:
            pass
        count = 0
        for cct in regData[reg].keys():
            figPath = path + "/" + str(count) + "-"
            draw(regData[reg][cct], c_prec=FreqOfMinEnergyRegion[reg][0], u_prec=FreqOfMinEnergyRegion[reg][1], title=cct, pre=figPath)
            count = count + 1

