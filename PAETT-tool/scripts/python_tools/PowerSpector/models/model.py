from abc import abstractmethod
import multiprocessing as mp
import numpy as np
import pickle

from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import StandardScaler

import datetime

def MAPE_debug(f, model, E_region):
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
        # print(key, inp[pred.argmin()][0], inp[pred.argmin()][1], E_pred, inp[np.argmin(energy)][0], inp[np.argmin(energy)][1], E_min)
        f.write("\npred:{0}-{1}  {2} \nreal:{3}-{4}   {5}\n\n".format(inp[pred.argmin()][0], inp[pred.argmin()][1], E_pred, inp[np.argmin(energy)][0], inp[np.argmin(energy)][1], E_min))
        mape += abs(E_pred-E_min)/E_min
    # mean
    mape /= len(E_region.keys())
    # To percentage
    mape *= 100 
    return mape

def MAPE(model, E_region):
    mape = 0
    for key in E_region.keys():
        energy = E_region[key][2]
        inp = E_region[key][3]
        trans = StandardScaler().fit_transform(np.array(inp))
        pred = model.predict(trans)
        E_pred = energy[pred.argmin()]
        E_min  = min(energy)
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

    def clear(self):
        self.model = None

    def load(self, path):
        self.model = None
        with open(path, "rb") as f:
            self.model = pickle.load(f)
        return self.model

    def save(self, name=None):
        if name is None:
            name = self.__class__.__name__ + '-' + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + '.pkl'
        print("Save model into: {0}".format(name))
        pickle.dump(self.model, open(name,"wb"))

    def LOOCV_test(self, dataset, out_filename):
        def test(q, self, datasets, b):
            model = self.init()
            assert(model is not None)
            # extract dataset
            I_train = datasets[b][0][0]
            O_train = datasets[b][0][1]
            I_test  = datasets[b][1][0]
            O_test  = datasets[b][1][1]
            # training
            print("[INFO] {0}: Training LOOCV...".format(b))
            model.fit(I_train,O_train)
            # prediction
            print("[INFO] {0}: Predict...".format(b))
            O_train_pred = model.predict(I_train)
            O_test_pred  = model.predict(I_test)
            print("[INFO] {0}: Calculate Loss...".format(b))
            train_loss = mean_absolute_error(O_train, O_train_pred)
            test_loss  = mean_absolute_error(O_test, O_test_pred)
            print("[INFO] {0}: Calculate MAPE...".format(b))
            mape = MAPE(model, dataset.data[b][2])
            print(" {0}: Train Loss={1}, Test Loss={2}, MAPE={3}\n".format(b, train_loss, test_loss, mape))
            q.put( mape )
        mape_list = []
        q = mp.Queue()
        pList = []
        datasets = dataset.LOOCV_split_dataset()
        for b in datasets.keys():
            p = mp.Process(target=test, args=(q,self,datasets,b,))
            p.start()
            pList.append(p)
        for p in pList:
            mape_list.append(q.get())
        for p in pList:
            p.join()
        # with open(out_filename, "w") as f:
        #     #print(data)
        #     datasets = dataset.LOOCV_split_dataset()
        #     #print(datasets)
        #     #print("111111111111111111")
        #     model = load("fine_tuneMLP.pkl")
        #     for b in datasets.keys():
        #         #model = GDBT_model_init()
        #         model = self.init()
        #         assert(model is not None)
        #         #model = Stack_model_init()
        #         # model = mlxstack()
        #         # extract dataset
        #         I_train = datasets[b][0][0]
        #         O_train = datasets[b][0][1]
        #         I_test  = datasets[b][1][0]
        #         O_test  = datasets[b][1][1]
        #         # training
        #         #print(O_train)
        #         print("INFO: Training LOOCV for {0}...".format(b), end='', flush=True)
        #         model.fit(I_train,O_train)
        #         # prediction
        #         print("Predict...", flush=True, end='')
        #         O_train_pred = model.predict(I_train)
        #         O_test_pred  = model.predict(I_test)
        #         print("Calculate Loss...", flush=True, end='')
        #         train_loss = mean_absolute_error(O_train, O_train_pred)
        #         test_loss  = mean_absolute_error(O_test, O_test_pred)
        #         print("Calculate MAPE...", flush=True)
        #         mape = MAPE(f, model, dataset.data[b][2])
        #         print(" {0}: Train Loss={1}, Test Loss={2}, MAPE={3}\n".format(b, train_loss, test_loss, mape))
        #         mape_list.append(mape)
        print("INFO: LOOCV average MAPE={0:.2f}".format(np.mean(mape_list)))

    def train(self, dataset):
        data = dataset.data
        I_train = []
        O_train = []
        for b in data.keys():
            I_train += data[b][0]
            O_train += data[b][1]
        I_train = np.array(I_train)
        O_train = np.array(O_train)
        self.model = self.init()
        self.model.fit(I_train, O_train)

        O_train_pred = self.model.predict(I_train)
        train_loss = mean_absolute_error(O_train, O_train_pred)
        print("\n Training Loss: ", train_loss)
        return self.model
    