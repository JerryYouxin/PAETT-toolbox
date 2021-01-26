from .model import ModelBase
import numpy as np
import math
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor

class StdMLPModel(ModelBase):
    def init(self, num=9, hidden=(5,5)):
        #model = MLPRegressor(hidden_layer_sizes=(5,5),activation='relu', solver='lbfgs', warm_start=True, max_iter=5000, early_stopping=True, random_state=10)max_iter=7000,
        #model = MLPRegressor(hidden_layer_sizes=(16,16),activation='relu', alpha=0.1,batch_size=128,beta_1=0.6,beta_2=0.2, solver='adam',learning_rate_init=1e-3, warm_start=True, max_iter=7000)
        print("INFO: Initializing MLP model")
        model = MLPRegressor(hidden_layer_sizes=(5,5),activation='relu',alpha=0.1,batch_size=128, solver='adam',learning_rate_init=1e-3, warm_start=True, max_iter=7000, early_stopping=True,random_state=70)
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
        model = Pipeline([('std',StandardScaler()),('model',model)])
        return model