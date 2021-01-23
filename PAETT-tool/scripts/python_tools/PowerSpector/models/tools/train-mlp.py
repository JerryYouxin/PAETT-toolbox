from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import GradientBoostingRegressor
import numpy as np

from sklearn.preprocessing import StandardScaler, PolynomialFeatures
import math

from sklearn.metrics import mean_absolute_error
import pickle
import os

from sklearn.pipeline import Pipeline

def read_data(benchmarks):
    res = {}
    for b in benchmarks:
        I_train = []
        O_train = []
        E_region= {}
        with open(b+"/metric.dat.2","r") as f:
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

def MLP_model_init(num=9, hidden=(5,5)):
    model = MLPRegressor(hidden_layer_sizes=(5,5),activation='relu', solver='lbfgs', warm_start=True, max_iter=5000, early_stopping=True, random_state=10)
    # model = MLPRegressor(hidden_layer_sizes=hidden,activation='relu', solver='adam', learning_rate_init=1e-5, warm_start=True, max_iter=1000, early_stopping=True)
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
    return Pipeline([('std',StandardScaler()),('model',model)])

def MLP_model_init_no_pipeline(num=9, hidden=(5,5)):
    model = MLPRegressor(hidden_layer_sizes=(5,5),activation='relu', solver='lbfgs', warm_start=True, max_iter=5000, early_stopping=True, random_state=10)
    # model = MLPRegressor(hidden_layer_sizes=hidden,activation='relu', solver='adam', learning_rate_init=1e-5, warm_start=True, max_iter=1000, early_stopping=True)
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
    return model

# model is MLP model, data_set small is data set without RAJA; data_set_all is data set with RAJA
def train_with_two(model, I_data_set_small, O_data_set_small, I_data_set_all, O_data_set_all):
    poly= PolynomialFeatures(2)
    std = StandardScaler()
    # first only fit standarizing with small data set without RAJA
    std.fit(poly.transform(I_data_set_small))
    # then transform the data
    I_preprocessed = std.transform(poly.transform(I_data_set_all))
    model.fit(I_preprocessed, O_data_set_all)
    return poly, std, model

def pack_MLP(poly, std, model):
    return Pipeline([('poly',poly), ('std',std), ("model",model)])

def GDBT_model_init():
    return Pipeline([('std',StandardScaler()),('model',GradientBoostingRegressor(loss='huber', learning_rate=0.1, n_estimators=80, subsample=0.8, max_depth=3, min_samples_split=130, min_samples_leaf=30, max_features=7, random_state=89))])

def MAPE(model, E_region):
    mape = 0
    for key in E_region.keys():
        energy = E_region[key][2]
        inp = E_region[key][3]
        pred = model.predict(np.array(inp))
        # print(pred)
        # print("\n")
        E_pred = energy[pred.argmin()]
        E_min  = min(energy)
        print(key, inp[pred.argmin()][0], inp[pred.argmin()][1], E_pred, inp[np.argmin(energy)][0], inp[np.argmin(energy)][1], E_min)
        mape += abs(E_pred-E_min)/E_min
    # mean
    mape /= len(E_region.keys())
    # To percentage
    mape *= 100 
    return mape

def LOOCV_test(data):
    datasets = LOOCV_split_dataset(data)
    for b in datasets.keys():
        # model = MLP_model_init()
        model = GDBT_model_init()
        # extract dataset
        I_train = datasets[b][0][0]
        O_train = datasets[b][0][1]
        I_test  = datasets[b][1][0]
        O_test  = datasets[b][1][1]
        # training
        model.fit(I_train, O_train)
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
    model = MLP_model_init()
    model.fit(I_train, O_train)
    O_train_pred = model.predict(I_train)
    train_loss = mean_absolute_error(O_train, O_train_pred)
    print("\n Training Loss: ", train_loss)
    return model

def save(model, name="MLP"):
    pickle.dump(model, open(name+'.pkl',"wb"))

def load(path):
    return pickle.load(path)

if __name__=="__main__":
    print("Reading Data...")
    NPB_data = read_data(["BT", "CG", "EP", "FT", "LU", "MG", "SP", "UA", "IS"])
    print("Filter dirty data...")
    NPB_data = filter_data(NPB_data, (22-8+1)*(20-7+1), 20)
    print("Begin LOOCV test")
    LOOCV_test(NPB_data)
    print("Begin training whole dataset")
    model = train(NPB_data)
    print("INFO: Save model to ./MLP.pkl")
    save(model, "MLP")
