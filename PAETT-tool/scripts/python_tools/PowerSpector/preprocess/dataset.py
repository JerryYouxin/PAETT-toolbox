from multiprocessing.context import Process
from multiprocessing.queues import Queue
import numpy as np
import pickle
import os
import multiprocessing as mp
import time
from sklearn.preprocessing import StandardScaler
from utils.Configuration import config

class Filter:
    @staticmethod
    def filter_data(data, test_num, energy_threshold, filter_same=False):
        checker = {}
        res = {}
        for b in data.keys():
            I_train = []
            O_train = []
            E_region_new = {}
            E_region= data[b][2]
            if not filter_same:
                # quick check first
                early_ret = True
                for key in E_region.keys():
                    if len(E_region[key][2]) != test_num:
                        early_ret = False
                        break
                    if min(E_region[key][2]) <= energy_threshold:
                        early_ret = False
                        break
                if early_ret:
                    res[b] = data[b]
                    print("{0}: No regions removed. Remain {1} regions.".format(b, len(E_region.keys())))
                    continue
            for key in E_region.keys():
                if filter_same:
                    check = str(E_region[key][3])
                    if check in checker.keys():
                        continue
                    checker[check] = 1 # mark the checker to filter out same data
                if len(E_region[key][2]) != test_num:
                    continue
                if min(E_region[key][2]) < energy_threshold:
                    continue
                # papi_val = E_region[key][3][-1][2:]
                E_region_new[key] = (E_region[key][0],E_region[key][1],E_region[key][2],[])
                for i in range(0,len(E_region[key][0])):
                    E_region_new[key][3].append([E_region_new[key][0][i], E_region_new[key][1][i]]+E_region[key][3][i][2:])
                I_train += E_region_new[key][3]
                O_train += E_region_new[key][2]
            print("{0}: Removed {1} regions containing dirty data, Remain {2} regions.".format(b,len(E_region.keys())-len(E_region_new.keys()), len(E_region_new.keys())))
            res[b] = (I_train, O_train, E_region_new)
        return res

    # find the outlier, and get the average value from its neighber in matrix
    @staticmethod
    def filter_energy(data,cmin,cmax,ucmin,ucmax):
        res = data

        c_min = cmin
        c_max = cmax
        uc_min = ucmin
        uc_max = ucmax
        line = uc_max - uc_min + 1

        f = open("strangepot","w")

        for b in data.keys():
            f.write("\nBENCHMARK NAME : {0} ----------------------------------------------{1}\n".format(b,b))
            E_region = data[b][2]
            for key in E_region.keys():
                E_val = E_region[key][2] #energy list
                s = np.std(E_val)
                mean = np.mean(E_val)
                E_rangemin = mean-s
                E_rangemax = mean+s
                D_val = []
                for c in range(c_min,c_max-1):
                    for uc in range(uc_min,uc_max-1):

                        ordernum = line*(c-c_min) + (uc-uc_min)
                        orderuc = line*(c-c_min) + (uc-(uc_min-1))
                        orderc = line*(c-(c_min-1)) + (uc-uc_min)
                        #print(ordernum,orderc,orderuc)
                        d_val1 = abs( E_val[orderc] - E_val[ordernum] )
                        D_val.append(d_val1)
                        d_val2 = abs( E_val[orderuc] - E_val[ordernum] )
                        D_val.append(d_val2)

                s_d = np.std(D_val)
                m_d = np.mean(D_val)

                max = m_d + s_d
                f.write("_____Region name : {0} , mean = {1} ,std={2} ,threadhold: {3},energy:{4}-----{5}__________\n".format(key,mean,s,max,E_rangemin,E_rangemax))

                #corner left up
                ordernum = 0
                orderuc1 = 1
                orderc1 = line
                d_val3 = abs( E_val[orderc1] - E_val[ordernum] )
                d_val4 = abs( E_val[orderuc1] - E_val[ordernum] )
                d_val = ( d_val3 + d_val4 ) / 2
                if d_val>max:
                    t = E_val[ordernum]
                    res[b][2][key][2][ordernum] = ( E_val[orderc1] + E_val[ordernum] + E_val[orderuc1] )/3   
                    f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,t,d_val,res[b][2][key][2][ordernum]) )
                #corner right down
                ordernum = line*(c_max-c_min) + (uc_max-uc_min)
                orderuc0 = line*(c_max-c_min) + (uc_max-(uc_min+1))
                orderc0 = line*(c_max-(c_min+1)) + (uc_max-uc_min)
                d_val1 = abs( E_val[orderc0] - E_val[ordernum] )
                d_val2 = abs( E_val[orderuc0] - E_val[ordernum] )
                d_val = ( d_val1 + d_val2 ) / 2
                if d_val>max:
                    t = E_val[ordernum]
                    res[b][2][key][2][ordernum] = ( E_val[orderc0] + E_val[ordernum] + E_val[orderuc0] )/3    
                    f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,t,d_val,res[b][2][key][2][ordernum]) )
                #corner left down
                ordernum = line*(c_max-c_min)
                orderuc1 = line*(c_max-c_min) + 1
                orderc0  = line*(c_max-(c_min+1))
                d_val1 = abs( E_val[orderc0] - E_val[ordernum] )
                d_val4 = abs( E_val[orderuc1] - E_val[ordernum] )
                d_val = ( d_val1 + d_val4 ) / 2
                if d_val>max:
                    t = E_val[ordernum]
                    res[b][2][key][2][ordernum] = ( E_val[orderc0] + E_val[ordernum] + E_val[orderuc1] )/3
                    f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,t,d_val,res[b][2][key][2][ordernum]) )
                #corner  right up
                ordernum = uc_max - uc_min
                orderuc0 = uc_max - ( uc_min+1 )
                orderc1 = line + (uc_max-uc_min)
                d_val2 = abs( E_val[orderuc0] - E_val[ordernum] )
                d_val3 = abs( E_val[orderc1] - E_val[ordernum] )
                d_val = ( d_val2 + d_val3 ) / 2
                if d_val>max:
                    t = E_val[ordernum]
                    res[b][2][key][2][ordernum] = ( E_val[orderc1] + E_val[ordernum] + E_val[orderuc0] )/3
                    f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,t,d_val,res[b][2][key][2][ordernum]) )
                #topline
                for uc in range(uc_min+1,uc_max):
                    c = c_min
                    ordernum = uc - uc_min
                    orderuc0 = uc - ( uc_min+1 )
                    orderuc1 = uc - ( uc_min-1 )
                    orderc1 = line + (uc-uc_min)
                    d_val2 = abs( E_val[orderuc0] - E_val[ordernum] )
                    d_val3 = abs( E_val[orderc1] - E_val[ordernum] )
                    d_val4 = abs( E_val[orderuc1] - E_val[ordernum] )
                    d_val = ( d_val2 + d_val3 + d_val4 ) / 3
                    if d_val>max:
                        t = E_val[ordernum]
                        res[b][2][key][2][ordernum] = ( E_val[orderuc0] + E_val[orderc1] + E_val[ordernum] + E_val[orderuc1] )/4
                        f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,t,d_val,res[b][2][key][2][ordernum]) )
                #downline
                for uc in range(uc_min+1,uc_max):
                    c = c_max
                    ordernum = line*( c - c_min ) + ( uc - uc_min )
                    orderuc0 = line*( c - c_min ) + ( uc - (uc_min+1) )#left
                    orderuc1 = line*( c - c_min ) + ( uc - (uc_min-1) )#right
                    orderc0 = line*( c - (c_min+1) ) + ( uc - uc_min )#up
                    d_val1 = abs( E_val[orderc0] - E_val[ordernum] )
                    d_val2 = abs( E_val[orderuc0] - E_val[ordernum] )
                    d_val4 = abs( E_val[orderuc1] - E_val[ordernum] )

                    d_val = ( d_val1 + d_val2 + d_val4 ) / 3
                    if d_val>max:
                        t = E_val[ordernum]
                        res[b][2][key][2][ordernum] = ( E_val[orderuc0] + E_val[ordernum] + E_val[orderuc1] + E_val[orderuc0] )/4
                        f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,t,d_val,res[b][2][key][2][ordernum]) )

                #leftline 
                for c in range(c_min+1,c_max):
                    uc = uc_min
                    ordernum = line*( c - c_min ) + ( uc - uc_min )
                    orderuc1 = line*( c - c_min ) + ( uc - (uc_min-1) )#right
                    orderc0 = line*( c - (c_min+1) ) + ( uc - uc_min )#up
                    orderc1 = line*( c - (c_min-1) ) + ( uc - uc_min )#down

                    d_val1 = abs( E_val[orderc0] - E_val[ordernum] )
                    d_val3 = abs( E_val[orderc1] - E_val[ordernum] )
                    d_val4 = abs( E_val[orderuc1] - E_val[ordernum] )

                    d_val = ( d_val1 + d_val3 + d_val4 ) / 3
                    if d_val>max:
                        t = E_val[ordernum]
                        res[b][2][key][2][ordernum] = ( E_val[orderuc0] + E_val[orderc1] + E_val[ordernum]  + E_val[orderuc1] )/4
                        f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,t,d_val,res[b][2][key][2][ordernum]) )
                #rightline
                for c in range(c_min+1,c_max):
                    uc = uc_max
                    ordernum = line*( c - c_max ) + ( uc - uc_min )
                    orderuc0 = line*( c - c_max ) + ( uc - (uc_min+1) )#left
                    orderc0 = line*( c - (c_max+1) ) + ( uc - uc_min )#up
                    orderc1 = line*( c - (c_max-1) ) + ( uc - uc_min )#down

                    d_val1 = abs( E_val[orderc0] - E_val[ordernum] )
                    d_val2 = abs( E_val[orderuc0] - E_val[ordernum] )
                    d_val3 = abs( E_val[orderc1] - E_val[ordernum] )

                    d_val = ( d_val1 + d_val2 + d_val3 ) / 3
                    if d_val>max:
                        t = E_val[ordernum]
                        res[b][2][key][2][ordernum] = ( E_val[orderuc0] + E_val[orderc1] + E_val[ordernum] + E_val[orderuc0] )/4
                        f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,t,d_val,res[b][2][key][2][ordernum]) )
                #middle pot
                for c in range(c_min+1,c_max-1):
                    for uc in range(uc_min+1,uc_max-1):
                        ordernum = line*( c - c_min ) + ( uc - uc_min )
                        orderuc0 = line*( c - c_min ) + ( uc - (uc_min+1) )#left
                        orderuc1 = line*( c - c_min ) + ( uc - (uc_min-1) )#right
                        orderc0 = line*( c - (c_min+1) ) + ( uc - uc_min )#up
                        orderc1 = line*( c - (c_min-1) ) + ( uc - uc_min )#down

                        d_val1 = abs( E_val[orderc0] - E_val[ordernum] )
                        d_val2 = abs( E_val[orderuc0] - E_val[ordernum] )
                        d_val3 = abs( E_val[orderc1] - E_val[ordernum] )
                        d_val4 = abs( E_val[orderuc1] - E_val[ordernum] )

                        d_val = ( d_val1 + d_val2 + d_val3 + d_val4 ) / 4
                        if d_val>max:
                            t = E_val[ordernum]
                            res[b][2][key][2][ordernum] = ( E_val[orderuc0] + E_val[orderc1] + E_val[ordernum] + E_val[orderuc0] + E_val[orderuc1] )/5   
                            f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,t,d_val,res[b][2][key][2][ordernum]) )
        f.close()
        return res


def _scale(args):
    key = args[0]
    labs = args[1]
    inps = args[2]
    labs_s = [ e / labs[-1] for e in labs ]
    metrics = []
    for line in inps:
        metrics.append(line[2:])
    metrics = np.transpose(StandardScaler().fit_transform(np.transpose(np.array(metrics)))).tolist()
    coreMean = (8+22)/2
    uncoreMean = (7+20)/2
    coreStd = np.std([ c for c in range(8, 23) ])
    uncoreStd = np.std([ f for f in range(7, 21) ])
    inps_s = []
    for i in range(len(inps)):
        # print(inps[i][:2], coreMean, uncoreMean, coreStd, uncoreStd)
        inps_s.append([(inps[i][0]-coreMean)/coreStd, (inps[i][1]-uncoreMean)/uncoreStd] + metrics[i])
    # print(inps_s)
    # inps_s = StandardScaler().fit_transform(np.array(inps)).tolist()
    return (key, labs_s, inps_s)

class DataSet:
    def __init__(self, cmin, cmax, ucmin, ucmax, benchmarks=[], energy_threshold=5, enable_correction=True, enable_cct=True, with_data_enhancement=False, enable_scale=True):
        self.data = {}
        self.cmin = cmin
        self.cmax = cmax
        self.ucmin= ucmin
        self.ucmax= ucmax
        p1 = "CCT" if enable_cct else "REG"
        p2 = "ENH" if with_data_enhancement else "NOE"
        self.cachePath = ".dataset.{0}.{1}.cache".format(p1, p2)        
        if len(benchmarks)>0:
            print("Loading data from benchmarks...")
            self.load(benchmarks, enable_cct, with_data_enhancement=with_data_enhancement)
            self.filter(cmin, cmax, ucmin, ucmax, energy_threshold, enable_correction)
            if enable_scale:
                self.scale()
            else:
                print("[INFO] scaling disabled")

    def scale(self):
        print("[INFO] Scaling each region/CCT's data...")
        data = {}
        for b in self.data.keys():
            print("[INFO] Scaling benchmark {0}".format(b))
            I_train = []
            O_train = []
            E_region = self.data[b][2]
            E_region_new = {}
            with mp.Pool(config.get_max_thread()) as p:
                res = p.map(_scale, [ (key, E_region[key][2], E_region[key][3]) for key in E_region.keys() ])
                for r in res:
                    key = r[0]
                    labs_s = r[1]
                    inps_s = r[2]
                    E_region_new[key] = (E_region[key][0], E_region[key][1], labs_s, inps_s)
                    O_train += labs_s
                    I_train += inps_s
            data[b] = (I_train, O_train, E_region_new)
        self.data = data

    def loadCache(self, root):
        path = root+"/"+self.cachePath
        if not os.path.exists(path):
            return None
        print("Cache Found for {0}: {1}".format(root, path))
        with open(path, "rb") as f:
            data = pickle.load(f)
        return data
    @staticmethod
    def loadCacheJob(q, root, cache):
        path = root + '/' + cache
        if not os.path.exists(path):
            return None
        print("Cache Found: {0}".format(path))
        with open(path, "rb") as f:
            data = pickle.load(f)
        q.put( (root,data) )

    def saveCache(self, data, root):
        path = root+"/"+self.cachePath
        print("Saving Cache to {0}".format(path))
        pickle.dump(data, open(path,"wb"))

    def _get_FreqSet(self, core, uncore):
        return str(core)+","+str(uncore)

    def _decode_FreqSet(self, freqSet):
        freq = freqSet.split(',')
        return int(freq[0]), int(freq[1])

    # Hot fix to split papi counter value along CCT (split_papi=True)
    def _split_papi(self, cct):
        children = cct[2:]
        for child in children:
            for k, c in child.items():
                if cct[0] is not None:
                    cct[0] = [ cct[0][i]-c[0][i] for i in range(len(cct[0])) ]
                    for v in cct[0]:
                        assert(v>=0)
                child[k] = self._split_papi(c)
        return cct
    # TODO: this split should be done in filter_significant_region tool
    def _load(self, bench, i, n, spacer, split_papi=True):
            CCT = {}
            with open(bench+"/metric.out","r") as f:
                core=0
                uncore=0
                lines = f.readlines()
                N = len(lines)
                I = 1
                preP = -1
                for line in lines:
                    if int(1000*float(I)/float(N))!=preP:
                        print(spacer.format(i, n, bench, 100*float(I)/float(N)), end='\r')
                        preP = int(10000*float(I)/float(N))
                    I = I + 1
                    cont = line.split(';')
                    if len(cont)<=0:
                        continue
                    if len(cont) >0:
                        keys = cont[:-1]
                        record = cont[-1].replace("\n","").split(' ')
                        core = int(record[0])
                        uncore = int(record[1])
                        assert(core!=0 and uncore!=0)
                        record = list(map(lambda x:float(x),record))

                        FreqSet = self._get_FreqSet(core, uncore)
                        if FreqSet not in CCT.keys():
                            CCT[FreqSet] = [None]
                        cct = CCT[FreqSet]
                        reg = keys[-1]
                        for k in keys[:-1]:
                            cct = cct[-1][k]
                        assert(len(cct)>=1)
                        if len(cct)==1 or (reg in cct[-1].keys()):
                            cct.append({reg: [record]})
                        else:
                            cct[-1][reg] = [record]
            if split_papi:
                for freqSet, cct in CCT.items():
                    CCT[freqSet] = self._split_papi(cct)
            return CCT

    def _load_reg(self, benchLoads, spacer, n, i):
        def mergeByReg(cct, data):
            children = cct[1:]
            for child in children:
                for k, c in child.items():
                    if c[0] is not None:
                        if k not in data.keys():
                            data[k] = c[0]
                        else:
                            data[k] = [ data[k][0], data[k][1] ] + [ data[k][i]+c[0][i] for i in range(2,len(data[k])) ]
                    mergeByReg(c, data)
        for b in benchLoads:
            i = i+1
            I_train = []
            O_train = []
            E_region= {}
            CCT = self._load(b, i, n, spacer)
            for freqSet, cct in CCT.items():
                core, uncore = self._decode_FreqSet(freqSet)
                data = {}
                mergeByReg(cct, data)
                for reg, dat in data.items():
                    if reg not in E_region.keys():
                        E_region[reg] = ([], [], [], [])
                    I_train.append(dat[:-1])
                    O_train.append(dat[-1])
                    E_region[reg][0].append(core)
                    E_region[reg][1].append(uncore)
                    E_region[reg][2].append(dat[-1])
                    E_region[reg][3].append(dat[:-1])
            self.data[b] = (I_train, O_train, E_region)
            self.saveCache(self.data[b], b)

    def _load_cct(self, benchLoads, spacer, n, i, with_data_enhancement):
        def cct2dict(cct, data, pre=""):
            children = cct[1:]
            cct_num = 0
            for child in children:
                if pre=="":
                    kpre = pre
                else:
                    kpre = pre+"-"+str(cct_num)+";"
                for k, c in child.items():
                    if c[0] is not None:
                        key = kpre+k
                        data[key] = c[0]
                    cct2dict(c, data, kpre+k)
                cct_num += 1
        def merge_metrics(a, b):
            return [a[0], a[1]] + [a[k]+b[k] for k in range(2, len(a))]
        for b in benchLoads:
            i = i+1
            I_train = []
            O_train = []
            E_region= {}
            CCT = self._load(b, i, n, spacer)
            for freqSet, cct in CCT.items():
                core, uncore = self._decode_FreqSet(freqSet)
                data = {}
                cct2dict(cct, data)
                # data enhancement:
                #   1. Add merged metrics along CCTs
                #   2. Add merged metrics of different numbers of CCTs from the same region
                if with_data_enhancement:
                    regMetrics = {}
                    dataItems = []
                    for key, dat in data.items():
                        # 1.1 collect ccts and metrics into a single list
                        ccts = key.split(';')
                        dataItems.append((ccts, dat))
                        # 2.1 collect metrics of different CCTs from the same region
                        reg = ccts[-1]
                        if reg not in regMetrics.keys():
                            regMetrics[reg] = [dat]
                        else:
                            regMetrics[reg]+= [dat]
                    # 1.2 Add merged metrics along CCTs
                    for ccts, dat in dataItems:
                        for j in range(1,len(ccts)):
                            k = ";".join(ccts[:j])
                            if k not in data.keys():
                                data[k] = dat
                            else:
                                data[k] = merge_metrics(data[k], dat)
                    # 2.2 Add merged metrics of different numbers of CCTs from the same region
                    for reg, metrics in regMetrics.items():
                        if len(metrics) > 1:
                            j = 0
                            base = metrics[0]
                            for dat in metrics[1:]:
                                j = j + 1
                                base = merge_metrics(base, dat)
                                key = reg+","+str(j)
                                data[key] = base
                for key, dat in data.items():
                    if key not in E_region.keys():
                        E_region[key] = ([], [], [], [])
                    I_train.append(dat[:-1])
                    O_train.append(dat[-1])
                    E_region[key][0].append(core)
                    E_region[key][1].append(uncore)
                    E_region[key][2].append(dat[-1])
                    E_region[key][3].append(dat[:-1])
            self.data[b] = (I_train, O_train, E_region)
            self.saveCache(self.data[b], b)

    def load(self, benchmarks, enable_cct=True, enable_cache=True, with_data_enhancement=False):
        n = len(benchmarks)
        i = 0
        maxlen = 0
        benchLoads = []
        data = None
        dataList = []
        start_time=time.time()
        for b in benchmarks:
            if enable_cache:
                data = self.loadCache(b)
            if data is None:
                benchLoads.append(b)
                if len(b) > maxlen:
                    maxlen = len(b)
            else:
                i = i+1
                self.data[b] = data
        end_time=time.time()
        print("Loading Cache time: {0:.4f} s".format(end_time-start_time))
        spacer = "Loading {{0}}/{{1}}: {{2:{}}}[{{3:5.1f}}%]".format(maxlen)
        if enable_cct:
            print("[INFO] Load data at CCT basis")
            self._load_cct(benchLoads, spacer, n, i, with_data_enhancement)
        else:
            print("[INFO] Load data at Region basis")
            self._load_reg(benchLoads, spacer, n, i)
        print("\nLoad Finish!")
        return self.data

    def filter(self, c_min, c_max, uc_min, uc_max, energy_threshold=5, enable_correction=True):
        print("Filtering data...")
        self.data = Filter.filter_data(self.data, (c_max-c_min+1)*(uc_max-uc_min+1), energy_threshold)
        if enable_correction:
            print("Filtering data with correction...")
            self.data = Filter.filter_energy(self.data,c_min,c_max,uc_min,uc_max)
        else:
            print("[INFO] Auto correction disabled")

    def LOOCV_split_dataset(self):
        data = self.data
        res = {}
        for b in data.keys():
            #print(b)
            if len(data[b][0])==0 or len(data[b][1])==0:
                print("\n Warning: {0}: has no test data! Skip LOOCV for this dataset.".format(b))
                continue
            test_data = (np.array(data[b][0]), np.array(data[b][1]))
            I_train = []
            O_train = []
            for t in data.keys():
                #print(t)
                if b!=t:
                    I_train += data[t][0]
                    O_train += data[t][1]
                    #print("________________________")
            if len(I_train)==0 or len(O_train)==0:
                print("\n Warning: {0}: has no training data! Skip LOOCV for this dataset.".format(b))
                continue
            train_data = (np.array(I_train), np.array(O_train))
            res[b] = (train_data, test_data)
        return res