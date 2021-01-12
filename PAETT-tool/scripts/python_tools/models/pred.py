from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import GradientBoostingRegressor
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import PolynomialFeatures
import math
from sklearn.metrics import mean_absolute_error
import pickle
import os
from sklearn.pipeline import Pipeline


#from sklearn.grid_search import GridSearchCV
from sklearn.model_selection import GridSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import StackingRegressor
from sklearn.linear_model import LassoCV
from sklearn.linear_model import LinearRegression

from mlxtend.regressor import StackingRegressor as stack
from mlxtend.data import boston_housing_data
from sklearn.svm import SVR



from sklearn.ensemble import BaggingRegressor
'''
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
#import tflearn
#import tflearn.datasets.mnist as mnist
'''

def read_data(benchmarks):
    res = {}
    for b in benchmarks:
        I_train = []
        O_train = []
        E_region= {}
        with open(b,"r") as f:
            core=0
            uncore=0
            for line in f:
                contori = line.split(';')
                if len(contori)==0:
                    continue
                if len(contori)==2:
                    cont = ( contori[1].replace("\n","") ).split(' ')
                    core=int(cont[0])
                    uncore=int(cont[1])
                    assert(core!=0 and uncore!=0)
                    record = []
                    key = contori[0]
                    # print(key)
                    if key not in E_region.keys():
                        E_region[key]=([],[],[],[])
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
        res[b] = (I_train, O_train, E_region)
        #print(res[b])
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
            # I_train += E_region[key][3]
            # O_train += E_region[key][2]
            # E_region_new[key] = E_region[key]
            # papi_val = []
            # for k in range(len(E_region[key][3][0])):
            #     papi_val.append([])
            # for i in range(len(E_region[key][3])):
            #     for k in range(len(E_region[key][3][i])):
            #         papi_val[k].append(E_region[key][3][i][k])
            # for k in range(len(E_region[key][3][0])):
            #     t = np.std(papi_val[k])
            #     papi_val[k] = (t, t/E_region[key][3][0][k])
            # print("Region ", key, " STD=", papi_val)
        print("{0}: Removed {1} regions containing dirty data, Remain {2} regions.".format(b,len(E_region.keys())-len(E_region_new.keys()), len(E_region_new.keys())))
        res[b] = (I_train, O_train, E_region_new)
    return res


# find the strange energy point, and get the average value from its neighber in matrix
def filter_energy(data):
    res = data

    c_min = 8
    c_max = 22
    uc_min = 7
    uc_max = 20
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
                res[b][2][key][2][ordernum] = ( E_val[orderc1] + E_val[ordernum] + E_val[orderuc1] )/3   
                f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,E_val[ordernum],d_val,res[b][2][key][2][ordernum]) )
            #corner right down
            ordernum = line*(c_max-c_min) + (uc_max-uc_min)
            orderuc0 = line*(c_max-c_min) + (uc_max-(uc-min+1))
            orderc0 = line*(c_max-(c_min+1)) + (uc_max-uc_min)
            d_val1 = abs( E_val[orderc0] - E_val[ordernum] )
            d_val2 = abs( E_val[orderuc0] - E_val[ordernum] )
            d_val = ( d_val1 + d_val2 ) / 2
            if d_val>max:
                res[b][2][key][2][ordernum] = ( E_val[orderc0] + E_val[ordernum] + E_val[orderuc0] )/3    
                f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,E_val[ordernum],d_val,res[b][2][key][2][ordernum]) )
            #corner left down
            ordernum = line*(c_max-uc_min)
            orderuc1 = line*(c_max-uc_min) + 1
            orderc0  = line*(c_max-(uc_min+1))
            d_val1 = abs( E_val[orderc0] - E_val[ordernum] )
            d_val4 = abs( E_val[orderuc1] - E_val[ordernum] )
            d_val = ( d_val1 + d_val4 ) / 2
            if d_val>max:
                res[b][2][key][2][ordernum] = ( E_val[orderc0] + E_val[ordernum] + E_val[orderuc1] )/3
                f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,E_val[ordernum],d_val,res[b][2][key][2][ordernum]) )
            #corner  right up
            ordernum = uc_max - uc_min
            orderuc0 = uc_max - ( uc_min+1 )
            orderc1 = line + (uc_max-uc_min)
            d_val2 = abs( E_val[orderuc0] - E_val[ordernum] )
            d_val3 = abs( E_val[orderc1] - E_val[ordernum] )
            d_val = ( d_val2 + d_val3 ) / 2
            if d_val>max:
                res[b][2][key][2][ordernum] = ( E_val[orderc1] + E_val[ordernum] + E_val[orderuc0] )/3
                f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,E_val[ordernum],d_val,res[b][2][key][2][ordernum]) )
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
                    res[b][2][key][2][ordernum] = ( E_val[orderuc0] + E_val[orderc1] + E_val[ordernum] + E_val[orderuc1] )/4
                    f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,E_val[ordernum],d_val,res[b][2][key][2][ordernum]) )
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
                    res[b][2][key][2][ordernum] = ( E_val[orderuc0] + E_val[ordernum] + E_val[orderuc1] + E_val[orderuc0] )/4
                    f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,E_val[ordernum],d_val,res[b][2][key][2][ordernum]) )

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
                    res[b][2][key][2][ordernum] = ( E_val[orderuc0] + E_val[orderc1] + E_val[ordernum]  + E_val[orderuc1] )/4
                    f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,E_val[ordernum],d_val,res[b][2][key][2][ordernum]) )
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
                    res[b][2][key][2][ordernum] = ( E_val[orderuc0] + E_val[orderc1] + E_val[ordernum] + E_val[orderuc0] )/4
                    f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,E_val[ordernum],d_val,res[b][2][key][2][ordernum]) )
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
                        res[b][2][key][2][ordernum] = ( E_val[orderuc0] + E_val[orderc1] + E_val[ordernum] + E_val[orderuc0] + E_val[orderuc1] )/5   
                        f.write( "Strange data: freq : {0}-{1};  Energy:{2}  dval:{3} ,newvalue{4}\n".format(c,uc,E_val[ordernum],d_val,res[b][2][key][2][ordernum]) )            
    f.close()
    return res

def LOOCV_split_dataset(data):
    res = {}
    for b in data.keys():
        test_data = (np.array(data[b][0]), np.array(data[b][1]))
        I_train = []
        O_train = []
        for t in data.keys():
            if b!=t:
                I_train += data[t][0]
                O_train += data[t][1]
        train_data = (np.array(I_train), np.array(O_train))
        res[b] = (train_data, test_data)
    return res

def MLP_model_init(num=55, hidden=(16,16,16)):
    #model = MLPRegressor(hidden_layer_sizes=(5,5),activation='relu', solver='lbfgs', warm_start=True, max_iter=5000, early_stopping=True, random_state=10)max_iter=7000,
    #model = MLPRegressor(hidden_layer_sizes=(16,16),activation='relu', alpha=0.1,batch_size=128,beta_1=0.6,beta_2=0.2, solver='adam',learning_rate_init=1e-3, warm_start=True, max_iter=7000)
    model = MLPRegressor(hidden_layer_sizes=(12,12),activation='relu',alpha=0.1,batch_size=128, solver='adam',learning_rate_init=1e-3, warm_start=True, max_iter=7000, early_stopping=True,random_state=70)
    # fake fit to obtain weights
    model.fit([[0 for i in range(num)] for k in range(1000)],[0 for i in range(1000)])
    for ii in range(len(model.coefs_)):
        dd = model.coefs_[ii].tolist()
        weight = []
        for d in dd:
            d2 = np.random.uniform(0,1,len(d))
            map(lambda x: x*math.sqrt(2/len(d2)), d2)
            weight.append(d2)
        model.coefs_[ii] = np.array(weight)
    for ii in range(len(model.intercepts_)):
        dd = model.intercepts_[ii].tolist()
        weight = []
        for d in dd:
            d2 = 0.0
            # d2 = np.random.uniform(0,1,1)[0]*math.sqrt(2)
            weight.append(d2)
        model.intercepts_[ii] = np.array(weight)
    # create pipeline to include preprocess
    return Pipeline([('polinomial',PolynomialFeatures(2)),('std',StandardScaler()),('model',model)])
    #return model

def GDBT_model_init():
    return Pipeline([('std',StandardScaler()),('model',GradientBoostingRegressor(loss='huber', learning_rate=0.1, n_estimators=80, subsample=0.8, max_depth=3, min_samples_split=130, min_samples_leaf=30, max_features=7, random_state=89))])

def MAPE(model, E_region):
    mape = 0
    for key in E_region.keys():
        f.write("region name:{0}________________________________________________\n".format(key))
        energy = E_region[key][2]
        inp = E_region[key][3]
        '''
        for i in range(0,210):
            f.write(str(inp[i]))
            f.write("\n")
        '''
        f.write("\n")


        f.write("energy:          \n")
        for i in range(7,21):
            f.write("          ")
            f.write("{:<3d}".format(i) )

        f.write("\n")

        for i in range(0,15):
            f.write("{:<10d}".format(i+8))
            for j in range(0,14):
                f.write("{:<10f}  ".format( float(energy[14*i+j]) ) )
            f.write("\n")

        pred = model.predict(np.array(inp))

        f.write("Pred_energy:          \n")
        for i in range(0,14):
            f.write("          ")
            f.write("{:<3d}".format(i+8) )

        f.write("\n")

        for i in range(0,15):
            f.write("{:<10d}".format(i+8))
            for j in range(0,14):
                f.write("{:<10f}  ".format( float(str(pred[14*i+j])) ) )
            f.write("\n")
        # print(pred)
        # print("\n")
        E_pred = energy[pred.argmin()]
        E_min  = min(energy)
        print(key, inp[pred.argmin()][0], inp[pred.argmin()][1], E_pred, inp[np.argmin(energy)][0], inp[np.argmin(energy)][1], E_min)
        f.write("\npred:{0}-{1}  {2} \nreal:{3}-{4}   {5}\n\n".format(inp[pred.argmin()][0], inp[pred.argmin()][1], E_pred, inp[np.argmin(energy)][0], inp[np.argmin(energy)][1], E_min))
        mape += abs(E_pred-E_min)/E_min
    # mean
    mape /= len(E_region.keys())
    # To percentage
    mape *= 100 
    return mape

def Stack_model_init():
    return StackingRegressor(estimators=[ ( 'GBDT',GDBT_model_init() ),( 'MLP',MLP_model_init() ) ], final_estimator=BaggingRegressor()  , n_jobs=-1)
    #LassoCV()

def mlxstack():
    model1 = GDBT_model_init()
    model2 = MLP_model_init()
    svr = SVR(kernel='rbf')
    return stack(regressors=[model1,model2],meta_regressor=svr)

def load(path):
    model = None
    with open(path, "rb") as f:
        model = pickle.load(f)
    return model

def LOOCV_test(data):
    datasets = LOOCV_split_dataset(data)
    model = load("fine_tuneMLP.pkl")
    for b in datasets.keys():
        # model = MLP_model_init()
        # model = mlxstack()
        # extract dataset
        I_train = datasets[b][0][0]
        O_train = datasets[b][0][1]
        I_test  = datasets[b][1][0]
        O_test  = datasets[b][1][1]
        # training
        # prediction
        O_train_pred = model.predict(I_train)
        O_test_pred  = model.predict(I_test)
        train_loss = mean_absolute_error(O_train, O_train_pred)
        test_loss  = mean_absolute_error(O_test, O_test_pred)
        mape = MAPE(model, data[b][2])
        print("\n {0}: Train Loss={1}, Test Loss={2}, MAPE={3}".format(b, train_loss, test_loss, mape))


def train(data):
    I_train = []
    O_train = []
    for b in data.keys():
        I_train += data[b][0]
        O_train += data[b][1]
    I_train = np.array(I_train)
    O_train = np.array(O_train)
    #model = GDBT_model_init()
    model = Stack_model_init()
    #model = mlxstack()
    model.fit(I_train, O_train)
    mape = MAPE(model, data[b][2])

    O_train_pred = model.predict(I_train)
    train_loss = mean_absolute_error(O_train, O_train_pred)
    print("\n Training Loss: ", train_loss)
    return model
'''
    std=StandardScaler()
    std.fit(I_train)
    #StandardScaler().fit(O_train)
    II_train = std.transform(I_train)
    #OO_train = StandardScaler().transform(O_train)



    #param_grid = {'batch_size':[32,64,96,128,160,192,224,256]}
    #param_grid = {'alpha':[1e-1,1e-2,1e-3,1e-4,1e-5,1e-6,1e-7],'learning_rate_init':[1e-2,1e-3,1e-4,1e-5,1e-6,1e-7,1e-8]}
    #param_grid = {'max_iter':range(1000,10000,1000)}
    param_grid = {'beta_1':[0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,0.99],'beta_2':[0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,0.99]}

    grid_search = GridSearchCV(model,param_grid,n_jobs=8,verbose=10)

    grid_search.fit(II_train,O_train)

    print(grid_search.best_params_,grid_search.best_score_)


    best_parameters = grid_search.best_estimator.get_params()
    for para,val in list(best_parameters.items()):
        print(para,val)
'''




def save(model, name="MLP"):
    pickle.dump(model, open(name+'.pkl',"wb"))





if __name__=="__main__":
    print("Reading Data...")
    #NPB_data = read_data(["BT", "CG", "EP", "FT", "MG", "SP", "IS"])
    #NPB_data = read_data(["BT", "CG", "EP", "FT", "LU", "MG", "SP", "UA", "IS","cfd","hotspot","nw","particlefilter","pathfinder","streamcluster"])
    #NPB_data = read_data(["BT", "CG", "EP", "FT", "LU", "MG", "SP", "UA","IS"])
    #NPB_data = read_data(["BT", "CG", "EP", "FT", "MG", "IS","BT-MZ","SP-MZ","cfd","heartwall","hotspot","leukocyte","lud","lavaMD","nw","particlefilter","pathfinder","srad","streamcluster"])
    #NPB_data = read_data(["BT", "CG", "EP", "FT", "LU", "MG","b+tree", "UA", "IS" ,"backprop","cfd20","heartwall","hotspot","hotspot3D","leukocyte","lud","lavaMD","nn20","nw20","particlefilter","pathfinder","srad","streamcluster20"])
    #NPB_data = read_data(["backprop","b+tree","cfd","heartwall","hotspot","hotspot3D","leukocyte","lud","lavaMD","nw","particlefilter","pathfinder","srad"])
    #NPB_data = read_data(["BT", "CG", "EP", "FT", "MG", "SP", "IS","cfd","hotspot","nw","particlefilter","pathfinder","streamcluster"])
    #NPB_data = read_data(["BT20", "CG", "EP", "FT", "IS", "MG","LU","UA", "BT-MZ", "SP-MZ","backprop","cfd20","heartwall","hotspot","hotspot3D","leukocyte","lud","lavaMD","nn20","nw20","particlefilter","pathfinder","srad","streamcluster20"])
    #NPB_data = read_data(["BT20", "CG", "EP", "IS","FT",  "MG","LU","UA", "BT-MZ", "SP-MZ","backprop","cfd","heartwall","hotspot","hotspot3D","leukocyte","lud","lavaMD","nn","nw","particlefilter","pathfinder","srad","streamcluster20"])
    #NPB_data = read_data(["BT","CG","EP","FT","IS","MG","BT-MZ","SP-MZ"])
    NPB_data = read_data(["QuEST" , "mgo"])
    print("Filter dirty data...")
    NPB_data = filter_data(NPB_data, (22-8+1)*(20-7+1), 20)

    f = open("predresult","w")

    print("find stgdata")
    NPB_data = filter_energy(NPB_data)

    #print("Begin LOOCV test")
    LOOCV_test(NPB_data)
    f.close()

    print("Begin training whole dataset")
    model = train(NPB_data)
    print("INFO: Save model to ./MLP.pkl")
    save(model, "MLP")
'''
'''
