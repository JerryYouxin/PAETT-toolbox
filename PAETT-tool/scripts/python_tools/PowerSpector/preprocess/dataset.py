import numpy as np
import pickle
import os

class Filter:
    @staticmethod
    def filter_data(data, test_num, energy_threshold):
        res = {}
        for b in data.keys():
            I_train = []
            O_train = []
            E_region_new = {}
            E_region= data[b][2]
            for key in E_region.keys():
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


class DataSet:
    def __init__(self, cmin, cmax, ucmin, ucmax, benchmarks=[], energy_threshold=5, enable_correction=True, enable_cct=True):
        self.data = {}
        self.cmin = cmin
        self.cmax = cmax
        self.ucmin= ucmin
        self.ucmax= ucmax
        self.cachePath = ".dataset.REG.cache"
        self.cachePathCCT = ".dataset.CCT.cache"
        if len(benchmarks)>0:
            print("Loading data from benchmarks...")
            self.load(benchmarks, enable_cct)
            self.filter(cmin, cmax, ucmin, ucmax, energy_threshold, enable_correction)

    def loadCache(self, root, enable_cct):
        path = root+"/"
        if enable_cct:
            path += self.cachePathCCT
        else:
            path += self.cachePath
        if not os.path.exists(path):
            return None
        print("Cache Found for {0}: {1}".format(root, path))
        with open(path, "rb") as f:
            data = pickle.load(f)
        return data

    def saveCache(self, data, root, enable_cct):
        path = root+"/"
        if enable_cct:
            path += self.cachePathCCT
        else:
            path += self.cachePath
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
            self.saveCache(self.data[b], b, enable_cct=False)

    def _load_cct(self, benchLoads, spacer, n, i):
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
            self.saveCache(self.data[b], b, enable_cct=True)
        # for b in benchLoads:
        #     i = i+1
        #     I_train = []
        #     O_train = []
        #     E_region= {}
        #     with open(b+"/metric.out","r") as f:
        #         core=0
        #         uncore=0
        #         lines = f.readlines()
        #         N = len(lines)
        #         I = 0
        #         preP = -1
        #         cct_counter = {}
        #         for line in lines:
        #             if int(1000*float(I)/float(N))!=preP:
        #                 print(spacer.format(i, n, b, 100*float(I)/float(N)), end='\r')
        #                 preP = int(10000*float(I)/float(N))
        #             I = I + 1
        #             cont = line.split(';')
        #             #print(contori)
        #             if len(cont)==0:
        #                 continue
        #             if len(cont) >0:
        #                 keys = cont[:-1]
        #                 record = cont[-1].replace("\n","").split(' ')
        #                 core = int(record[0])
        #                 uncore = int(record[1])
        #                 assert(core!=0 and uncore!=0)
        #                 record = list(map(lambda x:float(x),record))
        #                 key = ""
        #                 if enable_cct:
        #                     ikeys = 1
        #                     Nkeys = len(keys)
        #                     cct = "{0},{1},{2}".format(core, uncore, keys[0])
        #                     if cct not in cct_counter.keys():
        #                         cct_counter[cct] = 0
        #                     elif ikeys==Nkeys:
        #                         cct_counter[cct]+= 1
        #                     cct+= "-"+str(cct_counter[cct])
        #                     for k in keys[1:]:
        #                         ikeys+= 1
        #                         cct = cct + ';' + k
        #                         if cct not in cct_counter.keys():
        #                             cct_counter[cct] = 0
        #                         elif ikeys==Nkeys:
        #                             cct_counter[cct]+= 1
        #                         cct+= "-"+str(cct_counter[cct])
        #                     key = ','.join(cct.split(',')[2:])
        #                 else:
        #                     key = ";".join(keys)
        #                 if key not in E_region.keys():
        #                     E_region[key]=([],[],[],[])
        #                     #print(key)
        #                 I_train.append(record[:-1])
        #                 O_train.append(record[-1])
        #                 E_region[key][0].append(core)
        #                 E_region[key][1].append(uncore)
        #                 E_region[key][2].append(record[-1])
        #                 E_region[key][3].append(record[:-1])
        #             else:
        #                 continue
        #     self.data[b] = (I_train, O_train, E_region)
        #     self.saveCache(self.data[b], b)
        #     #print(res[b])

    def load(self, benchmarks, enable_cct=True, enable_cache=False):
        n = len(benchmarks)
        i = 0
        maxlen = 0
        benchLoads = []
        data = None
        for b in benchmarks:
            if enable_cache:
                data = self.loadCache(b, enable_cct)
            if data is None:
                benchLoads.append(b)
                if len(b) > maxlen:
                    maxlen = len(b)
            else:
                i = i+1
                self.data[b] = data
        spacer = "Loading {{0}}/{{1}}: {{2:{}}}[{{3:5.1f}}%]".format(maxlen)
        if enable_cct:
            print("[INFO] Load data at CCT basis")
            self._load_cct(benchLoads, spacer, n, i)
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