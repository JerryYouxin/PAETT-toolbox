import os
VERBOSE = False

class Configuration:
    def __init__(self):
        self.read_config()

    def read_config(self):
        self.config = {}
        with open(os.environ['ROOT_POWERSPECTOR_TOOL']+'/include/config.h', "r") as f:
            for line in f:
                if "#define" in line:
                    cont = line.split(' ')
                    if len(cont) == 3:
                        if '.' in cont[2]:
                            self.config[cont[1].strip()] = float(cont[2].strip())
                        else:
                            self.config[cont[1].strip()] = int(cont[2].strip())
        # checking necessary info
        for d in ['MAX_CORE_FREQ', 'MAX_UNCORE_FREQ', 'MIN_CORE_FREQ', 'MIN_UNCORE_FREQ']:
            if d not in self.config.keys():
                print(d+' is not defined in '+os.environ['ROOT_POWERSPECTOR_TOOL']+'/include/config.h file!')
                exit(1)
        self.printRange()
    
    def printRange(self):
        print("[Info] Core: {0}~{1}, Uncore: {2}~{3}".format(self.get_min_core(), self.get_max_core(), self.get_min_uncore(), self.get_max_uncore()))

    def get_max_core(self):
        return self.config['MAX_CORE_FREQ']

    def get_min_core(self):
        return self.config['MIN_CORE_FREQ']

    def get_max_uncore(self):
        return self.config['MAX_UNCORE_FREQ']

    def get_min_uncore(self):
        return self.config['MIN_UNCORE_FREQ']

    def get_max_thread(self):
        return self.config['NCPU']

config = Configuration()