import numpy as np
import math
import os

import matplotlib
import matplotlib.pyplot as plt
import os

import matplotlib.patches as patches

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
        print(core, uncore, energy)
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
            if emin > heatmaps[c][uc]:
                emin = heatmaps[c][uc]
                cm = c
                ucm = uc
    for c in range(0,15):
        for uc in range(0,14):
            if abs(heatmaps[c][uc]-emin) <= delta:
                clist.append(c)
                ulist.append(uc)
    print(cm, ucm)
    print(clist, ulist)
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
        pre += "#"
    ax2.set_title(title)
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
            if len(E_region[key][2]) != test_num:
                # print("Remove region {0} as it has incorrect number of records ({1} data needed but has {2})".format(key, test_num, len(E_region[key][2])))
                continue
            if min(E_region[key][2]) < energy_threshold:
                # print("Remove region {0} as it has too small energy values ({1} J, threshold={2} J)".format(key, min(E_region[key][2]), energy_threshold))
                continue
            # now use the maximum core/uncore's papi counter value as input (typically the last record)
            papi_val = E_region[key][3][-1][2:]
            E_region_new[key] = (E_region[key][0],E_region[key][1],E_region[key][2],[])
            for i in range(0,len(E_region[key][0])):
                    E_region_new[key][3].append([E_region_new[key][0][i], E_region_new[key][1][i]]+papi_val)
            I_train += E_region_new[key][3]
            O_train += E_region_new[key][2]
        print("{0}: Removed {1} regions containing dirty data, Remain {2} regions.".format(b,len(E_region.keys())-len(E_region_new.keys()), len(E_region_new.keys())))
        res[b] = (I_train, O_train, E_region_new)
    return res

def getStaticalRegionData(data):
    res = {}
    E_region = data[2]
    for key in E_region.keys():
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
    for key in E_region.keys():
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
        res[reg] = (core, uncore, energy)
    return res, reg2cct
    
def generate_frequency_commands(data, file_name):
    with open(file_name, "w") as f:
        f.write("1 ")
        for key in data.keys():
            f.write("{0} {1};{2} {3} {4} {5} {6} {7}\n".format(0, key, data[key][0]*100000, data[key][1]*256+data[key][1], 0, 0,0,0))

def parse_cct_to_insert_point(data):
    res = {}
    for key in data.keys():
        regions = key.split("=>")
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
    BENCH="QBOX/"
    data_src = "./data/"+BENCH
    print("Reading Data...")
    data = read_data([data_src])
    print("Filter dirty data...")
    data = filter_data(data, (22-8+1)*(20-7+1), 20)
    # data = filter_data(data, 4, 20)
    FreqOfMinEnergy = getFreqOfMinEnergy(data[data_src])
    FreqOfMinEnergyRegion, reg2cct = getFreqOfMinEnergyRegion(data[data_src])
    for reg in reg2cct.keys():
        if len(reg2cct[reg])>1:
            print(reg, FreqOfMinEnergyRegion[reg])
            tot_energy = 0
            cct_list = reg2cct[reg]
            for cct in cct_list:
                print("\t",cct, "\n\t  ", FreqOfMinEnergy[cct])
                tot_energy += FreqOfMinEnergy[cct][2]
            print("\tCCT-based Energy=",tot_energy, "J, Region-based Energy=", FreqOfMinEnergyRegion[reg][2],"J, Saving ", 100*(1-tot_energy/FreqOfMinEnergyRegion[reg][2]), "%")
    generate_frequency_commands(FreqOfMinEnergyRegion, data_src+"paett_model.cache.region")
    generate_frequency_commands(parse_cct_to_insert_point(FreqOfMinEnergy), data_src+"paett_model.cache.cct")
    # generate heatmap figures for further analysis
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

