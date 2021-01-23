import numpy as np

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
    def __init__(self, cmin, cmax, ucmin, ucmax, benchmarks=[], energy_threshold=5, enable_correction=True):
        self.data = {}
        self.cmin = cmin
        self.cmax = cmax
        self.ucmin= ucmin
        self.ucmax= ucmax
        if len(benchmarks)>0:
            print("Loading data from benchmarks...")
            self.load(benchmarks)
            self.filter(cmin, cmax, ucmin, ucmax, energy_threshold, enable_correction)

    def load(self, benchmarks):
        n = len(benchmarks)
        i = 0
        maxlen = 0
        for b in benchmarks:
            if len(b) > maxlen:
                maxlen = len(b)
        spacer = "Loading {{0:.2f}}%: {{1:{}}}".format(maxlen)
        for b in benchmarks:
            print(spacer.format(100*float(i)/float(n), b), end='\r')
            i = i+1
            I_train = []
            O_train = []
            E_region= {}
            with open(b+"/metric.out","r") as f:
                core=0
                uncore=0
                for line in f:
                    contori = line.split(';')
                    #print(contori)
                    if len(contori)==0:
                        continue
                    if len(contori) >0:
                        contori_back = contori
                        cont = ( contori[-1].replace("\n","") ).split(' ')
                        core=int(cont[0])
                        uncore=int(cont[1])
                        assert(core!=0 and uncore!=0)
                        record = []
                        #print(contori_back)
                        del(contori_back[-1])
                        #print(contori_back)
                        key = ''.join(contori_back)
                        #for i in range(len(contori)):
                        #    key += contori[i]

                        if key not in E_region.keys():
                            E_region[key]=([],[],[],[])
                            #print(key)
                        for s in cont:
                            record.append(float(s))
                        I_train.append(record[:-1])
                        O_train.append(record[-1])
                        E_region[key][0].append(core)
                        E_region[key][1].append(uncore)
                        E_region[key][2].append(record[-1])
                        E_region[key][3].append(record[:-1])
                    else:
                        continue
            self.data[b] = (I_train, O_train, E_region)
            #print(res[b])
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