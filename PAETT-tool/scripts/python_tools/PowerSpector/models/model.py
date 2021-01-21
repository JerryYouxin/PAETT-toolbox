from abc import abstractmethod
import numpy as np
import math
import pickle
import os
import sys

sys.path.append("..")
from utils.Configuration import config
from utils.executor import execute, get_metric_name
from utils.CallingContextTree import CallingContextTree, AdditionalData, load_keyMap
from utils.searcher import threadSearch, mergeMetrics, addThreadInfo

from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import PolynomialFeatures
from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import GradientBoostingRegressor

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

def MAPE(f, model, E_region):
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

class ModelBase:
    def __init__(self):
        self.model = None

    @abstractmethod
    def init(self):
        pass

    def load(self, path):
        self.model = None
        with open(path, "rb") as f:
            self.model = pickle.load(f)
        return self.model

    def LOOCV_test(self, data, out_filename):
        if self.model is None:
            raise ValueError(self.model)
        print("Begin LOOCV test")
        with open(out_filename, "w") as f:
            #print(data)
            datasets = data.LOOCV_split_dataset()
            #print(datasets)
            #print("111111111111111111")
            # model = load("fine_tuneMLP.pkl")
            for b in datasets.keys():
                #model = GDBT_model_init()
                model = self.model
                #model = Stack_model_init()
                # model = mlxstack()
                # extract dataset
                I_train = datasets[b][0][0]
                O_train = datasets[b][0][1]
                I_test  = datasets[b][1][0]
                O_test  = datasets[b][1][1]
                # training
                #print(O_train)
                model.fit(I_train,O_train)
                # prediction
                O_train_pred = model.predict(I_train)
                O_test_pred  = model.predict(I_test)
                train_loss = mean_absolute_error(O_train, O_train_pred)
                test_loss  = mean_absolute_error(O_test, O_test_pred)
                mape = MAPE(f, model, data[b][2])
                print("\n {0}: Train Loss={1}, Test Loss={2}, MAPE={3}".format(b, train_loss, test_loss, mape))

    def train(self, data):
        I_train = []
        O_train = []
        for b in data.keys():
            I_train += data[b][0]
            O_train += data[b][1]
        I_train = np.array(I_train)
        O_train = np.array(O_train)
        model = self.init()
        model.fit(I_train, O_train)

        O_train_pred = model.predict(I_train)
        train_loss = mean_absolute_error(O_train, O_train_pred)
        print("\n Training Loss: ", train_loss)
        return model
    