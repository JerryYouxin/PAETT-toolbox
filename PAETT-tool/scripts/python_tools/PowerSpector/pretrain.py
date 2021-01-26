from preprocess.dataset import DataSet
from models import MLPModel, GDBTModel
from utils.Configuration import config

import os
import shutil
import argparse

models = {
    'MLP': MLPModel,
    'GDBT': GDBTModel
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train pre-defined models from collected metrics (by collect_data)')
    parser.add_argument('--model', help='pre-defined models to train, including '+str(models.keys()), required=True)
    parser.add_argument('--benchmarks', help='collected data generated by collect_data. For multiple data from different benchmarks, split by ",".', default="")
    parser.add_argument('--data', help="data folder containing all collected data from all benchmarks.", default="COLLECT")
    parser.add_argument('--out', help="output model's file name", default=None)
    parser.add_argument('--configs', help="manual configuration in format (in 100MHz): <min core freq>,<max core freq>,<min uncore freq>,<max uncore freq> ", default="")
    parser.add_argument('--threshold', help="Energy threshold for filtering dirty data.", type=float, default=10.0)
    parser.add_argument('--enable_cct', help="Enable loading training data with CCT-awareness", action="store_true")
    parser.add_argument('--disable_cct', help="Disable loading training data with CCT-awareness", action="store_true")
    args = parser.parse_args()

    enable_cct = True
    if args.disable_cct:
        enable_cct = False

    if args.model not in models.keys():
        print("Error: unknown model: ", args.model)
        print("Error: Should be one of these pre-defined models: ", models.keys())
        exit(1)
    model = models[args.model]()
    
    benchmarks = []
    if args.benchmarks=="":
        if os.path.exists(args.data):
            if os.path.isdir(args.data):
                files = os.listdir(args.data)
                for file in files:
                    path = args.data + '/' + file
                    if os.path.isdir(path):
                        dataFiles = os.listdir(path)
                        if "metric.out" not in dataFiles:
                            print("INFO: Ignore directory {0} as it doesn't contain metric file (metric.out).".format(path))
                        else:
                            benchmarks.append(path)
                    else:
                        print("INFO: Ignore file {0} as it is not a data directory.".format(path)) 
            else:
                print("Error: {0} is not a data directory!".format(args.data))
                exit(1)
        else:
            print("Error: directory '{0}' not exist.".format(args.data))
            exit(1)
    else:
        benchmarks = args.benchmarks.split(',')
    if len(benchmarks) == 0:
        print("Error: no benchmarks are found!")
        exit(1)
    print("Using benchmarks: ", benchmarks)
    cmin = config.get_min_core()
    cmax = config.get_max_core()
    ucmin= config.get_min_uncore()
    ucmax= config.get_max_uncore()
    if args.configs!="":
        freqs = args.configs.split(',')
        if len(freqs)==4:
            cmin = int(freqs[0])
            cmax = int(freqs[1])
            ucmin= int(freqs[2])
            ucmax= int(freqs[3])
            print("Using Core: {0}~{1}, Uncore: {2}~{3}".format(cmin, cmax, ucmin, ucmax))
        else:
            print('Error: format error for --configs!')
            exit(1)
    dataset = DataSet(cmin, cmax, ucmin, ucmax, benchmarks=benchmarks, energy_threshold=args.threshold, enable_correction=True)
    # LOOCV test
    print("Begin LOOCV test")
    model.LOOCV_test(dataset, "predresult")
    # train with whole dataset
    print("Begin training")
    model.train(dataset)
    # save
    print("Saving trained model")
    model.save(args.out)

    