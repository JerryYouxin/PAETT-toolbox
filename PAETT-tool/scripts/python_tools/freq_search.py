#!python3
import numpy as np
import os
import subprocess
import shutil
import sys
from getopt import getopt

VERBOSE=False
keyMap =None

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
                print(d+' is not defined in ../include/config.h file!')
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

# global configurations
config = Configuration()

def make_core(core):
    if core==0:
        return 0
    if core<config.get_min_core():
        core = config.get_min_core()
    if core>config.get_max_core():
        core = config.get_max_core()
    return core*100000

def make_uncore(uncore):
    if uncore==0:
        return 0
    if uncore<config.get_min_uncore():
        uncore = config.get_min_uncore()
    if uncore>20:
        uncore = config.get_max_uncore()
    return uncore*256+uncore

class MetricData:
    def __init__(self):
        total_num = (config.get_max_core()-config.get_min_core()+1)*(config.get_max_uncore()-config.get_min_uncore()+1)
        self.data = [ 1000000000 for i in range(0, total_num) ]
        self.energy = {}
    
    def _make_index(self, core, uncore):
        return (core-config.get_min_core())*(config.get_max_uncore()-config.get_min_uncore()+1) + (uncore-config.get_min_uncore())

    def _decode_index(self, index):
        return int(index / (config.get_max_uncore()-config.get_min_uncore()+1)) + config.get_min_core(), index % (config.get_max_uncore()-config.get_min_uncore()+1) + config.get_min_uncore()

    def fill(self, core, uncore, energy):
        if core!=0 and uncore!=0: 
            self.data[self._make_index(core, uncore)] = energy
            self.energy["{0} {1}".format(core, uncore)] = energy
    
    def add(self, core, uncore, energy):
        if core!=0 and uncore!=0: 
            key = "{0} {1}".format(core, uncore)
            if key not in self.energy.keys():
                self.energy[key] = energy
                self.data[self._make_index(core, uncore)] = energy
            else:
                self.energy[key]+= energy
                self.data[self._make_index(core, uncore)]+= energy

    def get(self, core, uncore):
        key = "{0} {1}".format(core, uncore)
        if key not in self.energy.keys():
            return 0
        return self.energy[key]

    def getMinFreq(self):
        assert(len(self.energy.keys())>0)
        return self._decode_index(np.argmin(self.data))

    def size(self):
        return len(self.energy.keys())

    def is_valid(self, core, uncore):
        if core<config.get_min_core() or core>config.get_max_core() or uncore<config.get_min_uncore() or uncore>config.get_max_uncore():
            return False
        return True
    
    def is_filled(self, core, uncore):
        return ("{0} {1}".format(core, uncore) in self.energy.keys())

    def save(self, file):
        for k in self.energy.keys():
            file.write("{0} {1} ".format(k, self.energy[k]))

def get_energy(node):
    return  node.metric.get(node.core, node.uncore)

class CallingContextTree:
    def __init__(self, name="ROOT", parent=None):
        self.name = name
        self.core  = 0
        self.uncore= 0
        self.thread= 0
        self.tuning= True
        self.parent= parent
        self.pruned= False
        self.lock  = False
        self.metric= MetricData() 
        self.child = {}
        self.__candidates = []
        self._core_min = 0
        self._uncore_min = 0
        self._thread_min = 0
        self._energy_min = None
        self._exclude = []
        self.grandTruth = None
        self.__similiar_candidates = []
        self.__core_step = 2
        self.__uncore_step = 2
        # Calling contexts
        self.next = self
        self.last = None
        self.start_index = 0
        self.end_index = -1
        self.cur_index = 0
        # this is reserved for any additional message stored in a node
        self.additional = None

    def update_if_min(self, energy):
        # # update by application's energy
        # if (self._energy_min is None) or self._energy_min > energy:
        #     if VERBOSE and (self._core_min!=self.core or self._uncore_min!=self.uncore or self._thread_min!=self.thread):
        #         print("-- Update: {0} {1} {2} {3} => {4} {5} {6}".format(self.name, self._core_min, self._uncore_min, self._thread_min, self.core, self.uncore, self.thread))
        #     self._core_min = self.core
        #     self._uncore_min = self.uncore
        #     self._thread_min = self.thread
        #     self._energy_min = energy
        # update by region-level energy
        # print(self.metric.get(self.core, self.uncore), self.metric.get(self._core_min, self._uncore_min))
        if (self._energy_min is None) or self.metric.get(self.core, self.uncore) < self.metric.get(self._core_min, self._uncore_min):
            if VERBOSE and (self._core_min!=self.core or self._uncore_min!=self.uncore or self._thread_min!=self.thread):
                print("-- Update: {0} {1} {2} {3} => {4} {5} {6}".format(self.name, self._core_min, self._uncore_min, self._thread_min, self.core, self.uncore, self.thread))
            self._core_min = self.core
            self._uncore_min = self.uncore
            self._thread_min = self.thread
            self._energy_min = energy
        # similiar regions
        # if (self._energy_min is not None) and self.tuning and self._energy_min!=energy:
        #     e  = self.metric.get(self.core, self.uncore)
        #     em = self.metric.get(self._core_min, self._uncore_min)
        #     if (e-em)/em < 0.02:
        #         self.__similiar_candidates.append( (self.core, self.uncore) )
        #         print("-- Region {0}: Adding {1} {2} into similiar minimum")
        for r in self.child.keys():
            self.child[r].update_if_min(energy)
    
    def __getOrInsertNode(self, key, start_index, end_index):
        # print("^^^^^ ",self.cur_index)
        self.cur_index += 1
        if self.end_index!=-1 and self.cur_index > self.end_index:
            #print(self, self.next==self)
            #print(self.cur_index, self.next.end_index, self.next.start_index, self.start_index, self.end_index)
            assert(self.next==self or (self.next!=self and self.end_index!=-1))
            assert(self.next==self or self.cur_index <= self.next.end_index)
            if self.cur_index >= self.next.start_index and self.cur_index <= self.next.end_index:
                assert(start_index == self.next.start_index)
                assert(end_index == self.next.end_index)
                self.next.cur_index = self.cur_index
                return self.next
            else:
                nxt = CallingContextTree(name=self.name, parent=self.parent)
                self.next = nxt
                nxt.last = self
                nxt.cur_index = self.cur_index
                nxt.start_index = start_index
                nxt.end_index = end_index
                if VERBOSE:
                    print("[{0}] Inserting new node into linked list: start={1}, end={2}, cur={3}".format(self.name,start_index, end_index, self.cur_index))
                    print("[Info:{3}] Last node of linked list: start={0}, end={1}, cur={2}".format(self.start_index, self.end_index, self.cur_index,self))
                assert(start_index>self.end_index)
                assert(start_index<=self.cur_index and (end_index==-1 or end_index>=self.cur_index))
                # now all variables are initialized, we can now return
                return nxt
        if not (start_index==0 and end_index==-1):
            # print(self, start_index, end_index, self.start_index, self.end_index)
            assert(start_index == self.start_index)
            assert(end_index == self.end_index)
        return self

    def getOrInsertChild(self, key, start_index=0, end_index=-1):
        assert(end_index==-1 or start_index<=end_index)
        # print("=-=-=-=-=-= before -=-=-=-=-=-=-")
        # self.print()
        # print("=-=-=-=-=-=-=-=-=-=-=---=-=-=-=-")
        if key not in self.child.keys():
            self.child[key] = CallingContextTree(key, self)
            self.child[key].start_index = start_index
            self.child[key].end_index = end_index
            self.child[key].cur_index = start_index
            assert(start_index==0)
        else:
            self.child[key] = self.child[key].__getOrInsertNode(key, start_index, end_index)
        # print("=-=-=-=-=-=-=-=-=-=-=-=-")
        # self.print()
        # print("=-=-=-=-=-=-=-=-=-=-=---")
        return self.child[key]

    def getFirstNode(self):
        p=self
        while p.last!=None:
            p = p.last
        return p

    def reset_nodes(self):
        p=self.getFirstNode()
        while p.next!=p:
            p.__reset_nodes()
            p = p.next
        p.__reset_nodes()

    def __reset_nodes(self):
        # print("$$$$",self, self.cur_index, self.start_index, self.end_index)
        self.cur_index = self.start_index-1
        for k in self.child.keys():
            self.child[k].reset_nodes()
            self.child[k] = self.child[k].getFirstNode()

    def fillMetric(self, core, uncore, energy, method="add"):
        assert(core!=0 and uncore!=0)
        if self.lock and (self.parent is not None):
            self.parent.fillMetric(core, uncore, energy, method)
            return
        if self.metric is None:
            self.metric = MetricData()
        if method=="add":
            self.metric.add(core, uncore, energy)
        elif method=="fill":
            self.metric.fill(core, uncore, energy)
        else:
            assert(False)
        if VERBOSE:
            print("\t{0} Fill Metric {1} {2} {3}, Size={4}".format(self.name, core, uncore, energy, self.metric.size()))

    def find(self, path):
        if path[-1]!=self.name:
            return None
        if len(path)==1 or (path[-2] not in self.child.keys()):
            return self
        return self.child[path[-2]].find(path[:-1])

    def add_candidate(self, coff, ucoff):
        if self.tuning and self.metric.is_valid(self.core+coff, self.uncore+ucoff):
            self.__candidates.append( (self.core+coff, self.uncore+ucoff) )
        for r in self.child.keys():
            self.child[r].add_candidate(coff,ucoff)

    def step(self):
        if self.tuning and self._energy_min is not None:
            self.core   = self._core_min
            self.uncore = self._uncore_min
            print("Region {0}: change to {1} {2}".format(self.name, self.core, self.uncore))
        elif self.tuning and self.metric is not None:
            if self.metric.size()>0:
                if VERBOSE:
                    print(self.name, self.core, self.uncore, self.thread, end=' => ')
                self.core, self.uncore = self.metric.getMinFreq()
                if VERBOSE:
                    print(self.core, self.uncore, self.thread)
            else:
                self.tuning = False
        for r in self.child.keys():
            self.child[r].step()

    def next_candidate(self):
        changed = False
        if len(self.__candidates)>0:
            self.core, self.uncore = self.__candidates.pop()
            if VERBOSE:
                print("-- Region {0}: Trying {1} {2}".format(self.name, self.core, self.uncore))
            changed = True
        for r in self.child.keys():
            # only one at a time
            # changed = changed or (self.child[r].next_candidate())
            changed = (self.child[r].next_candidate()) or changed
        return changed

    # ###
    # #O#
    # ###
    def get_candidate_9cell(self):
        self.__candidates = []
        for c in [self.core-1, self.core, self.core+1]:
            for uc in [self.uncore-1, self.uncore, self.uncore+1]:
                if (self.metric is not None) and self.metric.is_valid(c, uc):
                    if not self.metric.is_filled(c, uc):
                        # print(c, uc, self.core, self.uncore)
                        self.__candidates.append( (c,uc) )
        while len(self.__similiar_candidates) > 0:
            core, uncore = self.__similiar_candidates.pop()
            for c in [core-1, core, core+1]:
                for uc in [uncore-1, uncore, uncore+1]:
                    if (self.metric is not None) and self.metric.is_valid(c, uc):
                        if not self.metric.is_filled(c, uc) and ((c,uc) not in self.__candidates):
                            self.__candidates.append( (c,uc) )
        print("-- Region {0}: Candidate core/uncore comb: ".format(self.name), self.__candidates)
        return len(self.__candidates)>0
    #       #
    #      ###
    #     ##O##
    #      ###
    #       #
    def get_candidate_13cell(self):
        self.__candidates = []
        for c in range(self.core-2, self.core+2+1):
            if (self.metric is not None) and self.metric.is_valid(c, self.uncore):
                if not self.metric.is_filled(c, self.uncore):
                    # print(c, uc, self.core, self.uncore)
                    self.__candidates.append( (c,self.uncore) )
        for uc in range(self.uncore-2, self.uncore+2+1):
            if (self.metric is not None) and self.metric.is_valid(self.core, uc):
                if not self.metric.is_filled(self.core, uc):
                    # print(c, uc, self.core, self.uncore)
                    self.__candidates.append( (self.core,uc) )
        for i in [-1, 1]:
            for j in [-1, 1]:
                c = self.core+i
                uc= self.uncore+j
                if (self.metric is not None) and self.metric.is_valid(c, uc):
                    if not self.metric.is_filled(c, uc):
                        self.__candidates.append( (c,uc) )
        print("-- Region {0}: Candidate core/uncore comb: ".format(self.name), self.__candidates)
        return len(self.__candidates)>0

    def get_candidate(self):
        self.__candidates = []
        while len(self.__candidates)==0 and self.__core_step>=0 and self.__uncore_step>0:
            if self.__core_step >= self.__uncore_step:
                uc = self.uncore
                for c in range(self.core-self.__core_step, self.core+self.__core_step+1):
                    if (self.metric is not None) and self.metric.is_valid(c, uc):
                        if not self.metric.is_filled(c, uc):
                            self.__candidates.append( (c,uc) )
                if len(self.__candidates)==0:
                    self.__core_step -= 1
            else:
                c = self.core
                for uc in range(self.uncore-self.__uncore_step, self.uncore+self.__uncore_step+1):
                    if (self.metric is not None) and self.metric.is_valid(c, uc):
                        if not self.metric.is_filled(c, uc):
                            self.__candidates.append( (c,uc) )
                if len(self.__candidates)==0:
                    self.__uncore_step -= 1
        print("-- Region {0}: Candidate core/uncore comb: ".format(self.name), self.__candidates)
        return len(self.__candidates)>0

    def get_tuningNodeList(self):
        res = []
        if self.tuning:
            res.append(self)
        for r in self.child.keys():
            res += self.child[r].get_tuningNodeList()
        return res

    def get_tuningNodeListInEnergyOrder(self):
        res = self.get_tuningNodeList()
        res.sort(key=get_energy)
        return res

    def get_max_energy_node(self, tot_energy, exclude):
        me = 99999999
        res= None
        if self.tuning and self not in exclude:
            me = self.metric.get(self.core, self.uncore) / tot_energy
            res= self
        for r in self.child.keys():
            node, ce = self.child[r].get_max_energy_node(tot_energy, exclude)
            if (node is not None) and node.tuning and (me >= ce):
                me = ce
                res = node
        if res is not None:
            print(self.name, res.name, me)
        else:
            print(self.name, res, me)
        return res, me

    def prepare_candidates_only_max(self, tot_energy):
        node, energy = self.get_max_energy_node(tot_energy, self._exclude)
        if node is None:
            return False
        node.get_candidate()
        node.tuing = (len(self.__candidates)>0)
        while not node.tuning:
            print("\tTurn off tuning of {0} as it has converged: {1} {2} {3}".format(node.name, node.core, node.uncore, node.thread))
            self._exclude.append(node)
            node, energy = self.get_max_energy_node(tot_energy, self._exclude)
            if node is None:
                return False
            node.get_candidate()
            node.tuing = (len(node.__candidates)>0)
        return True

    # return [(core, uncore)]
    def prepare_candidates(self):
        print("-- ", self.name, self.tuning)
        if self.tuning:
            self.get_candidate()
            self.tuning = (len(self.__candidates)!=0)
            if not self.tuning:
                print("\tTurn off tuning of {0} as it has converged: {1} {2} {3}".format(self.name, self.core, self.uncore, self.thread))
        hasCandidates=self.tuning
        for r in self.child.keys():
            # flag = self.child[r].prepare_candidates()
            # hasCandidates = flag or hasCandidates
            hasCandidates = hasCandidates or self.child[r].prepare_candidates()
        # print(self.name, hasCandidates, self.__candidates)
        return hasCandidates

    def save(self, file):
        self.__saveTo(file)
        # file.write("{0} {1} {2} {3} ".format(self.name, self.core, self.uncore, self.thread))
        # self.metric.save(file)
        # file.write("{0}\n".format(len(self.child.keys())))
        # for r in self.child.keys():
        #     self.child[r].save(file)
    
    def __saveNodeTo(self, file, pre=""):
        key = self.name
        file.write(pre+"Enter;{0};{1};{2};{3} {4} {5}\n".format(key, self.start_index, self.end_index, make_core(self.core), make_uncore(self.uncore), self.thread))
        for r in self.child.keys():
            self.child[r].__saveTo(file, pre+'  ')
        file.write(pre+"Exit\n")

    def __saveTo(self, file, pre=""):
        p = self
        while p!=p.next:
            p.__saveNodeTo(file, pre)
            p = p.next
        p.__saveNodeTo(file, pre)
            
        # if self.core!=-1 and (not self.pruned):
        #     key = self.name
        #     for k in pre:
        #         file.write(str(k)+";")
        #     file.write("{0};{1} {2} {3}\n".format(key, self.core, self.uncore, self.thread))
        #     for r in self.child.keys():
        #         self.child[r].__saveTo(file, pre+[key])

    def saveTo(self, file_name):
        p = self
        while 'ROOT' in p.child.keys():
            p = p.child['ROOT']
        with open(file_name, "w", newline="") as file:
            p.__saveTo(file)

    def loadFrom(self, file_name):
        self.reset_nodes()
        p = self
        with open(file_name, "r") as f:
            for line in f:
                cont = line.split(";")
                command = cont[0].strip()
                if command=="Enter":
                    key     = cont[1]
                    start   = int(cont[2])
                    end     = int(cont[3])
                    # UNSIGNED_INT_MAX is -1
                    if end == 4294967295:
                        end = -1
                    vals = cont[-1].split(" ")
                    # TODO: Need to figure out why empty string is generated from profile
                    if(key==''):
                        continue
                    p = p.getOrInsertChild(key, start, end)
                    p.core = int(vals[0])
                    p.uncore = int(vals[1])
                    p.thread = int(vals[2])
                elif command=="Exit":
                    p = p.parent
                else:
                    print("Error: Unknown command '{0}' in file: {1}".format(command, file_name))
                    exit(1)
        self.reset_nodes()

    def __generate_frequency_commands(self, file, keyMap, pre):
        key = keyMap[self.name]
        if self.pruned:
            file.write(pre+"Enter {0} {1} {2} {3} {4} {5}\n".format(key, self.start_index, self.end_index, 0, 0, 0))
        else:
            file.write(pre+"Enter {0} {1} {2} {3} {4} {5}\n".format(key, self.start_index, self.end_index, make_core(self.core), make_uncore(self.uncore), self.thread))
        for r in self.child.keys():
            self.child[r].generate_frequency_commands(file, keyMap, pre+'  ')
        file.write(pre+"Exit\n")

    def generate_frequency_commands(self, file, keyMap, pre=""):
            # if self.core!=-1 and (not self.pruned):
            #     print(self.name)
        p = self
        while p!=p.next:
            p.__generate_frequency_commands(file, keyMap, pre)
            p = p.next
        p.__generate_frequency_commands(file, keyMap, pre)

    def __generate_frequency_commands_with(self, file, keyMap, core, uncore, thread, pre=""):
        key = keyMap[self.name]
        if self.pruned:
            file.write(pre+"Enter {0} {1} {2} {3} {4} {5}\n".format(key, self.start_index, self.end_index, 0, 0, 0))
        else:
            file.write(pre+"Enter {0} {1} {2} {3} {4} {5}\n".format(key, self.start_index, self.end_index, make_core(core), make_uncore(uncore), thread))
        for r in self.child.keys():
            self.child[r].generate_frequency_commands_with(file, keyMap, core, uncore, thread, pre+'  ')
        file.write(pre+"Exit\n")

    def generate_frequency_commands_with(self, file, keyMap, core, uncore, thread, pre=""):
        p = self
        while p!=p.next:
            p.__generate_frequency_commands_with(file, keyMap, core, uncore, thread, pre)
            p = p.next
        p.__generate_frequency_commands_with(file, keyMap, core, uncore, thread, pre)

    def __str__(self):
        return self.name

    def __print(self, pre):
        comments = ""
        if self.tuning:
            comments += "[tuning]"
        if self.pruned:
            comments += "[pruned]"
        print(pre+"+ ", self.name, [self.start_index, self.end_index, self.cur_index], (self.core, self.uncore, self.thread), comments )
        for r in self.child.keys():
            self.child[r].print(pre+"|   ")
    
    def print(self, pre=""):
        p=self.getFirstNode()
        while(p!=p.next):
            p.__print(pre)
            p=p.next
        p.__print(pre)

    def optimize(self, lock=False):
        may_prune = True
        for r in self.child.keys():
            may_prune = self.child[r].optimize(lock) and may_prune
        if may_prune:
            if self.parent is not None:
                may_prune = ((self.core==self.parent.core) and (self.uncore==self.parent.uncore) and (self.thread==self.parent.thread))
                # print(self.name, (self.core, self.uncore, self.thread), self.parent.name, (self.parent.core, self.parent.uncore, self.parent.thread), may_prune )
            may_prune = may_prune or (self.core<=0 and self.uncore<=0 and self.thread<=0)
        self.pruned = may_prune
        if lock and self.pruned:
            self.lock = True
            self.tuning = False
        return self.pruned

    def recover(self):
        if not self.lock:
            self.pruned = False
        for r in self.child.keys():
            self.child[r].recover()
    
    def reset_freq(self):
        p = self
        while p!=p.next:
            p.core=0
            p.uncore=0
            for r in p.child.keys():
                p.child[r].reset_freq()
            p = p.next
        p.core=0
        p.uncore=0
        for r in p.child.keys():
            p.child[r].reset_freq()
    
    def reset_thread(self):
        self.thread=0
        p = self
        while p!=p.next:
            for r in p.child.keys():
                p.child[r].reset_thread()
            p = p.next
        for r in p.child.keys():
            p.child[r].reset_thread()

    def check(self, tot_energy, threshold=0.01):
        if self.metric.get(self.core, self.uncore) / tot_energy < threshold:
            if VERBOSE and self.tuning:
                print("\tTurn off tuning of {0} as it has too small energy consomption: {1} {2} {3} ({4} %)".format(self.name, self.core, self.uncore, self.metric.get(self.core, self.uncore), 100 * self.metric.get(self.core, self.uncore) / tot_energy))
            self.tuning = False
        for r in self.child.keys():
            self.child[r].check(tot_energy)

    def standardize(self):
        if self.core==0:
            self.tuning = False
            if self.parent is not None:
                self.core = self.parent.core
            else:
                self.core = config.get_max_core() # max
        if self.uncore==0:
            self.tuning = False
            if self.parent is not None:
                self.uncore = self.parent.uncore
            else:
                self.uncore = config.get_max_uncore() # max
        if self.thread==0:
            self.tuning = False
            if self.parent is not None:
                self.thread = self.parent.thread
            # else:
            #     self.thread = config.get_max_thread() # max
        for r in self.child.keys():
            self.child[r].standardize()

def load_thread_cct_freqcommand(cct_fn, keymap_fn):
    keymap = {}
    with open(keymap_fn, "r") as f:
        for line in f:
            cont = line.split(" ")
            keymap[cont[0]] = " ".join(cont[1:])[:-1]
    cct = CallingContextTree()
    with open(cct_fn, "r") as f:
        for line in f:
            cont = line.split(" ")
            n = int(cont[0])
            p = cct
            for i in range(0, n):
                reg = keymap[cont[i+1]]
                p.name = reg
                if i==n-1:
                    p.core = int(int(cont[n+1])/100000) # core
                    p.uncore = int(cont[n+2])&0xff # uncore
                    p.thread = int(cont[n+3]) # thread
                else:
                    p = p.getOrInsertChild(keymap[cont[i+2]])
    # standarize cct
    if VERBOSE:
        cct.print()
    cct.standardize()
    cct.optimize(lock=True)
    if VERBOSE:
        print("---------------")
        cct.print()
        print("---------------")
    return cct

def load_thread_cct(cct_fn):
    cct = CallingContextTree()
    cct.loadFrom(cct_fn)
    # standarize cct
    if VERBOSE:
        cct.print()
    # cct.standardize()
    # cct.optimize()
    if VERBOSE:
        print("---------------")
        cct.print()
        print("---------------")
    return cct

def load_cct_from_metrics(cct, metric_fn, thread=0, core=-1, uncore=-1, target="energy"):
    if cct is None:
        cct = CallingContextTree()
    cct.reset_nodes()
    # print('=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=')
    # cct.print()
    # print('=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-')
    if core<0:
        core = config.get_max_core()
    if uncore<0:
        uncore = config.get_max_uncore()
    def update_energy(p, energy, time):
        return (p.additional is None) or (energy < p.additional[1]) or (energy==p.additional[1] and thread>p.thread)
    def update_edp(p, energy, time):
        return (p.additional is None) or (energy*time < p.additional[1]*p.additional[2]) or (energy*time==p.additional[1]*p.additional[2] and thread>p.thread)
    update = None
    if target=="energy":
        update = update_energy
    elif target=="edp":
        update = update_edp
    else:
        raise ValueError("unknown target")
    # pointer of calling context tree used for iteration
    p = cct
    updated = False
    with open(metric_fn,"r") as f:
        for line in f:
            cont = line.split(' ')
            if len(cont)==0:
                continue
            record = []
            cont = line.split(';')
            command = cont[0].strip()
            if command=="Enter":
                key   = cont[1]
                start = int(cont[2])
                end   = int(cont[3])
                tnum  = int(cont[4])
                # UNSIGNED_INT_MAX is -1
                if end == 4294967295:
                    end = -1
                cont  = cont[5].split(' ')
                for s in cont:
                    record.append(float(s))
                metric = record[:-2]
                time = record[-2]
                energy = record[-1]
                if key=='':
                    print("Error: ", key)
                    print("-- line=\"{0}\"".format(line))
                    print("-- key=\"{0}\"".format(key))
                    exit(1)
                p = p.getOrInsertChild(key, start, end)
                # print(p, start, p.start_index, end, p.end_index)
                assert(start==p.start_index)
                assert(end==p.end_index)
                if update(p, energy, time):
                    p.additional = (metric, energy, time)
                    # if thread>0:
                    #     p.thread = thread if tnum>1 else 1
                    if thread>0:
                        p.thread = thread
                    else:
                        p.thread = tnum
                    p.core = core
                    p.uncore = uncore
                    updated = True
            elif command=="Exit":
                p = p.parent
            else:
                print("Error: Unknown command '{0}' in frequency command file: {1}".format(command, metric_fn))
                exit(1)
    if updated:
        cct.print()
    return cct

def __get_cct_energy(cct):
    tot_energy = 0
    if cct.additional is not None:
        tot_energy += cct.additional[1]
    for r in cct.child.keys():
        tot_energy += get_cct_energy(cct.child[r])
    return tot_energy

def get_cct_energy(cct):
    tot_energy = 0
    p = cct.getFirstNode()
    while p!=p.next:
        tot_energy += __get_cct_energy(p)
        p = p.next
    tot_energy += __get_cct_energy(p)
    return tot_energy

def generate_cct_frequency_commands(cct, name):
    while 'ROOT' in cct.child.keys():
        cct = cct.child['ROOT']
    cct.optimize() # optimize CCT to generate optimized commands
    if VERBOSE:
        print("------------ GENERATED CCT TO {0} -----------".format(name+".cct"))
        cct.print()
        print("---------------------------------------------")
    with open(name+".cct", "w", newline='') as f:
        cct.generate_frequency_commands(f, keyMap)
    cct.recover() # recover CCT as optimized commands may also can be fine tuned later
    return name+".cct"

def load_keyMap(fn):
    keyMap = {"ROOT":-1}
    with open(fn, "r") as f:
        for line in f:
            cont = line[:-1].split(" ")
            key = int(cont[0])
            name= " ".join(cont[1:])
            keyMap[name] = key
    return keyMap

# run and log energy metrics
def exec_once(exe, cct, keymap_fn, update=True):
    res_fn = "metric.dat.search"
    tmp_cct_fn = "frequency_command.tmp"
    tmp_cct_fn = generate_cct_frequency_commands(cct, tmp_cct_fn)
    os.environ['PAETT_CCT_FREQUENCY_COMMAND_FILE'] = tmp_cct_fn
    os.environ['PAETT_ENABLE_FREQMOD'] = 'ENABLE'
    # only collect energy information
    os.environ['PAETT_PROFILE_EVENTS'] = 'ENERGY'
    exe += " > paett-run.log"
    if VERBOSE:
        print("-- Running: ", exe)
    subprocess.check_call(exe, shell=True)
    cmd = "freq_set {0} {1}".format(str(config.get_max_core()), str(config.get_max_uncore()))
    subprocess.check_call(cmd, shell=True)
    subprocess.check_call("sleep 1", shell=True)
    subprocess.check_call("rm -rf "+res_fn, shell=True)
    if keymap_fn is not None:
        cmd = "filter_significant_profile --keymap_fn "+keymap_fn + " > " + res_fn
    else:
        cmd = "filter_significant_profile > " + res_fn
    subprocess.check_call(cmd, shell=True)
    tot_energy = 0.0
    # now read the profile and fill in energy info
    with open(res_fn, "r") as f:
        for line in f:
            record = []
            cont = line.split(';')
            key = cont[0]
            cont = cont[1].split(' ')
            for s in cont:
                record.append(float(s))
            energy = record[-1]
            path = key.split("=>")[:-1]
            node = cct.find(path)
            assert(node is not None)
            # print(key, path, node.name)
            node.fillMetric(node.core, node.uncore, energy)
            tot_energy += energy
    print("\n-- Total Energy Consumption: ", tot_energy, " J")
    cct.check(tot_energy)
    if update:
        cct.update_if_min(tot_energy)
    return tot_energy

# update cct's core/uncore value and give the next step
def hill_climbing(exe, cct, keymap_fn, max_iter=5, max_cct_num=5):
    i = 1
    energy = exec_once(exe, cct, keymap_fn)
    # tuning list: [small_energy_node, ..., large_energy_node]
    nodeList = cct.get_tuningNodeListInEnergyOrder()
    try:
        cn = 1
        print("-- INFO: {0} regions needed to be tuned".format(len(nodeList)))
        while True:
            if max_cct_num>0 and cn > max_cct_num:
                print("-- INFO: Max number of cct reached.")
                break
            if len(nodeList) == 0:
                print("-- INFO: All CCTs are converged.")
                break
            i = 1
            print("-- INFO: ", nodeList)
            node = nodeList.pop() # get cct node with the largest energy consumption in the list
            print("-- Region {0}: {1} {2} {3}".format(node.name, node.core, node.uncore, get_energy(node)))
            while node.get_candidate():
                if max_iter>0 and i>max_iter:
                    print("-- INFO: Max iteration count reached.")
                    break
                print("-- Region {0}: Iter: {1} / {2}".format(node.name, i, max_iter))
                while cct.next_candidate():
                    E = exec_once(exe, cct, keymap_fn)
                    if E<energy:
                        energy = min([E, energy])
                        generate_cct_frequency_commands(cct, "hill_climbing."+str(E))
                cct.step()
                print("-- INFO: Minimal Energy consumption: {0}".format(energy))
                # cct.print()
                generate_cct_frequency_commands(cct, "hill_climbing."+str(cn)+"."+str(i))
        # while True:
        #     if max_iter>0 and i > max_iter:
        #         print("-- INFO: Max iteration count reached.")
        #         break
        #     print("-- Iter: {0} / {1}".format(i, max_iter))
        #     node = nodeList.pop()
        #     while len(nodeList) > 0 and (not node.get_candidate()):
        #         node = nodeList.pop()
        #     #if not cct.prepare_candidates():
        #     #if not cct.prepare_candidates_only_max(energy):
        #     if len(nodeList) == 0:
        #         # converged, early stop
        #         print("-- INFO: Converged")
        #         break
        #     while(cct.next_candidate()):
        #         E = exec_once(exe, cct, keymap_fn)
        #         energy = min([E, energy])
        #     cct.step()
        #     with open("cct.tmp."+str(i),"w") as f:
        #         cct.save(f)
        #     cct.print()
        #     generate_cct_frequency_commands(cct, "hill_climbing.cct."+str(i))
        #     i = i + 1
    except KeyboardInterrupt:
        print("-- Warning: keyboardinterrupt detected. Store current resolutions.")
        with open("hill_climbing.cct.tmp","w") as f:
            cct.save(f)
        cct.print()
        generate_cct_frequency_commands(cct, "hill_climbing.cct")
        sys.exit(1)

def grid_search(exe, cct, keymap_fn, grid_size=2):
    cct.add_candidate(0, 0)
    for c in range(-grid_size, grid_size+1):
        for uc in range(-grid_size, grid_size+1):
            if c!=0 or uc!=0:
                cct.add_candidate(c, uc)
    checkpoint = 0
    while(cct.next_candidate()):
        checkpoint += 1
        exec_once(exe, cct, keymap_fn)
        if checkpoint % 10 == 0:
            with open("grid_search.tmp."+str(checkpoint), "w") as f:
                cct.save(f)
    with open("grid_search.cct","w") as f:
        cct.save(f)
    cct.step()
    # cct.print()

def get_metric_name(pre, core, uncore, tnum):
    return "{0}metric.dat.{1}.{2}.{3}".format(pre,core,uncore,tnum)

# execute *exe* with *tnum* threads
# the number of threads will be sent as the last argument of *exe*
# and OMP_NUM_THREADS will automatically set to the tnum
def exec(exe, tnum, core, uncore, keymap_fn, out_dir='./', papi_events=[], cct_fn=None, res_fn=None, enable_freqmod=True, generate_keymap=False):
    if res_fn==None:
        res_fn = get_metric_name(out_dir,core, uncore, tnum)
    os.environ.pop('PAETT_DETECT_MODE', 'Not-found')
    os.environ['KMP_AFFINITY']='granularity=fine,compact'
    if tnum>0:
        os.environ['OMP_NUM_THREADS'] = str(tnum)
    else:
        os.environ.pop('OMP_NUM_THREADS', 'Not-found')
    if cct_fn is not None:
        os.environ['PAETT_CCT_FREQUENCY_COMMAND_FILE'] = cct_fn
    else:
        os.environ.pop('PAETT_CCT_FREQUENCY_COMMAND_FILE', 'Not-found')
    os.environ['PAETT_DEFAULT_CORE_FREQ'] = str(core)
    os.environ['PAETT_DEFAULT_UNCORE_FREQ'] = str(uncore)
    if enable_freqmod:
        os.environ['PAETT_ENABLE_FREQMOD'] = 'ENABLE'
    else:
        os.environ['PAETT_ENABLE_FREQMOD'] = 'DISABLE'
    if generate_keymap:
        os.environ['PAETT_KEYMAP_PATH'] = keymap_fn
    else:
        os.environ.pop('PAETT_KEYMAP_PATH', 'Not-found')
    # if PAPI profiling is not needed, we just disable this
    events = "ENERGY"
    for pe in papi_events:
        events = events + ";" + pe
    os.environ['PAETT_PROFILE_EVENTS'] = events
    exe += " > paett-run.log."+str(tnum)
    if tnum>0:
        exe = "numactl --physcpubind=0-{0} ".format(tnum-1) + exe
    if VERBOSE:
        print("-- Running: ", exe)
    cmd = "freq_set {0} {1}".format(str(core), str(uncore))
    subprocess.check_call(cmd, shell=True)
    subprocess.check_call("sleep 1", shell=True)
    if tnum>0:
        subprocess.check_call("{0} {1}".format(exe, str(tnum)), shell=True)
    else:
        subprocess.check_call(exe, shell=True)
    subprocess.check_call("rm -rf "+res_fn, shell=True)
    if keymap_fn is not None:
        cmd = "filter_significant_profile --keymap_fn "+keymap_fn + " > " + res_fn
    else:
        cmd = "filter_significant_profile > " + res_fn
    subprocess.check_call(cmd, shell=True)
    return res_fn

# [start, end], with step size *step*
def thread_search(exe, keymap_fn, start, end, step, enable_consistant_thread, enable_continue, thread_res_fn="thread.cct", target="energy"):
    # temporary metric output files
    out_dir = 'thread_metrics/'
    if enable_continue:
        if not os.path.exists(out_dir):
            print("Warning: continue enabled but no existing output directory found! Disable continue and restart searching.")
            enable_continue = False
            os.mkdir(out_dir)
    else:
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        os.mkdir(out_dir)
    # add single thread execution as baseline
    print("Running with 1 Thread")
    res_fn = get_metric_name(out_dir, config.get_max_core(), config.get_max_uncore(), 1)
    if not (enable_continue or os.path.exists(res_fn)):
        res_fn = exec(exe, 1, config.get_max_core(), config.get_max_uncore(), keymap_fn, out_dir)
    cct = load_cct_from_metrics(None, res_fn, 1, target=target)
    energy = get_cct_energy(cct)
    if start==1:
        start = start + step
    for i in range(start, end+1, step):
        print("Running with {0} Thread".format(i))
        res_fn = get_metric_name(out_dir, config.get_max_core(), config.get_max_uncore(), i)
        if not (enable_continue or os.path.exists(res_fn)):
            tmp_cct_fn = "frequency-tmp.cct"
            with open(tmp_cct_fn, 'w') as f:
                cct.generate_frequency_commands_with(f, keyMap, config.get_max_core(), config.get_max_uncore(), i)
            res_fn = exec(exe, i, config.get_max_core(), config.get_max_uncore(), keymap_fn, out_dir, cct_fn=tmp_cct_fn)
        # thread configuration must be consistant across all ccts
        if enable_consistant_thread:
            # if consistant thread is enabled, we do not tune the thread number at runtime
            # as it may cause application's undefined behaviors (e.g. segfault, undesired low utility)
            cct_tmp = load_cct_from_metrics(None, res_fn, i, target=target)
            # set global settings as temporary return values, need to be cleared outside
            cct_tmp.thread = i
            energy_tmp = get_cct_energy(cct_tmp)
            if energy_tmp < energy:
                print("Update to Thread {0}, energy {1} J".format(i, energy_tmp))
                cct = cct_tmp
                energy = energy_tmp
        else:
            cct = load_cct_from_metrics(cct, res_fn, i, target=target)
    cct.reset_nodes()
    if thread_res_fn is not None:
        print("Save thread optimized cct to ", thread_res_fn)
        cct.saveTo(thread_res_fn)
        # with open(thread_res_fn, "w", newline='') as f:
        #     cct.generate_frequency_commands(f, keyMap)
    return cct

def exaustive_search(exe, cct, keymap_fn, enable_continue, thread_num=0, enable_thread=False, target="energy"):
    out_dir = 'metrics/'
    if enable_continue:
        if not os.path.exists(out_dir):
            print("Warning: continue enabled but no existing output directory found! Disable continue and restart searching.")
            enable_continue = False
            os.mkdir(out_dir)
    else:
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        os.mkdir(out_dir)
    thread_list = [thread_num]
    cct.reset_nodes()
    if enable_thread:
        thread_list = [ i for i in range(1,config.get_max_thread()) ]
        cct.reset_thread()
    cct.reset_freq()
    # cct.optimize()
    tmp_cct_fn = "frequency_command.tmp"
    tmp_cct_fn = generate_cct_frequency_commands(cct, tmp_cct_fn)
    for t in thread_list:
        for c in range(config.get_min_core(), config.get_max_core()+1):
            for uc in range(config.get_min_uncore(), config.get_max_uncore()+1):
                print("-- [Info] Trying core={0}, uncore={1}, thread={2}".format(c, uc, t))
                res_fn = get_metric_name(out_dir, c, uc, t)
                if not (enable_continue and os.path.exists(res_fn)):
                    res_fn = exec(exe, t, c, uc, keymap_fn, out_dir=out_dir, cct_fn=tmp_cct_fn, res_fn=res_fn)
                # cct.print()
                cct = load_cct_from_metrics(cct, res_fn, t, c, uc, target=target)
    cct.reset_nodes()
    cct.optimize()
    if VERBOSE:
        print("-- [INFO] Exaustive search finished. Final CCT frequency command: ")
        cct.print()
    return cct

def exec_static(exe, tnum, core, uncore, use_perf=False):
    if tnum>0:
        os.environ['OMP_NUM_THREADS'] = str(tnum)
    else:
        os.environ.pop('OMP_NUM_THREADS', 'Not-found')
    cmd = "freq_set {0} {1}".format(str(core), str(uncore))
    subprocess.check_call(cmd, shell=True)
    subprocess.check_call("sleep 1", shell=True)
    if use_perf:
        if tnum>0:
            subprocess.check_call("{ "+"perf stat -e energy-pkg {0} {1} 2>&1; ".format(exe, str(tnum))+"} > log", shell=True)
        else:
            subprocess.check_call("{ "+"perf stat -e energy-pkg {0} 2>&1; ".format(exe)+"} > log", shell=True)
    else:
        if tnum>0:
            subprocess.check_call("{ "+"collect_energy {0} {1} 2>&1; ".format(exe, str(tnum))+"} > log", shell=True)
        else:
            subprocess.check_call("{ "+"collect_energy {0} 2>&1; ".format(exe)+"} > log", shell=True)
    energy = 0
    time = 0
    if use_perf:
        with open("log","r") as f:
            for line in f:
                if "Joules energy-pkg" in line:
                    cont = line.split()
                    energy = float(cont[0].replace(',',''))
                if "seconds time elapsed" in line:
                    cont = line.split()
                    time = float(cont[0].replace(',',''))
    else:
        with open("collect_energy.log", "r") as f:
            line = f.readline()
            cont = line.split(',')
            energy = float(cont[0].replace(',',''))
            time = float(cont[1].replace(',',''))
    return energy, time

def thread_search_static(exe, start, end, step):
    thread = 1
    emin = 10000000
    tmin = 10000000
    if start==1:
        print("Running with 1 Thread")
        emin, tmin = exec_static(exe, 1, config.get_max_core(), config.get_max_uncore())
        start+=step
    for i in range(start, end+1, step):
        print("Running with {0} Thread".format(i))
        e, t = exec_static(exe, i, config.get_max_core(), config.get_max_uncore())
        if emin > e or (emin==e and tmin>t):
            emin = e
            tmin = t
            thread = i
    return thread

def static_search(exe, tnum=0, enable_thread=False):
    thread_list = [tnum]
    if enable_thread:
        thread_list = [ i for i in range(1,config.get_max_thread()) ]
    emin = None
    tmin = None
    core = None
    uncore = None
    for n in thread_list:
        for c in range(config.get_min_core(), config.get_max_core()+1):
            for uc in range(config.get_min_uncore(), config.get_max_uncore()+1):
                print("-- [Info] Trying core={0}, uncore={1}, thread={2}".format(c, uc, n))
                e, t = exec_static(exe, n, c, uc)
                if emin is None or emin>e or (emin==e and tmin>t):
                    print("-- [Info] Update: thread={0}, core={1}, uncore={2} (energy={3}, time={4})".format(n,c,uc,e,t))
                    emin, tmin, tnum, core, uncore = e, t, n, c, uc
    return tnum, core, uncore


def usage():
    return

if __name__=="__main__":
    keymap_fn = "PAETT.keymap"
    cct_src = "thread.cct"
    exe = "./run.sh"
    out_fn = "frequency_command"
    use_hill = False
    use_grid = False
    use_exaustive = False
    grid_size = 2
    max_iter = -1
    read_only= False
    thread_only = False
    thread_begin = 2
    thread_end = config.get_max_thread()
    thread_step = 2
    use_thread_search = True
    use_static = False
    enable_consistant_thread = False
    enable_continue = False
    out_dir = "metrics"
    freq_command = None
    target = "energy"
    opts, args = getopt(sys.argv[1:], "hvk:c:o:r:", ["help", "target=", "keymap=","cct-src=","output=", "run=", "exaustive", "hill-climbing", "grid-search", "grid-size=", "max-iter=", "read-only", "thread-only", "tbegin=", "tend=", "tstep=", "static", "consistant-thread", "continue", "freqcomm="])
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit(1)
        if opt=="-v":
            VERBOSE=True
        elif opt in ("-k", "--keymap"):
            keymap_fn = arg
        elif opt in ("-c", "--cct-src"):
            cct_src = arg
            use_thread_search = False
        elif opt in ("-o", "--output"):
            out_fn = arg
        elif opt in ("-r", "--run"):
            exe = arg
        elif opt == "--static":
            use_static=True
        elif opt == "--grid-search":
            use_grid = True
        elif opt == "--hill-climbing":
            use_hill = True
        elif opt == "--exaustive":
            use_exaustive = True
        elif opt == "--continue":
            enable_continue = True
        elif opt == "--grid-size":
            grid_size = int(arg)
        elif opt == "--max-iter":
            max_iter = int(arg)
        elif opt == "--read-only":
            read_only= True
        elif opt == "--thread-only":
            thread_only = True
        elif opt == "--tbegin":
            thread_begin = int(arg)
        elif opt == "--tend":
            thread_end = int(arg)
        elif opt == "--tstep":
            thread_step = int(arg)
        elif opt == "--consistant-thread":
            enable_consistant_thread = True
        elif opt=="--freqcomm":
            freq_command = arg
            use_thread_search = False
        elif opt=="--target":
            target = arg
        else:
            print("Error: Unknown option: ", opt)
            usage()
            sys.exit(1)
    if use_thread_search:
        print("[Info] Thread Search Enabled")
    if use_static:
        print("Searching for optimal static configuration...")
        if use_thread_search:
            thread_num = thread_search_static(exe, thread_begin, thread_end, thread_step)
        else:
            thread_num = int(os.environ['OMP_NUM_THREADS'])
            print("Thread Search disabled. Use OMP_NUM_THREADS={0}", thread_num)
        if thread_only:
            print("[Info] Thread only enabled. Skip core/uncore frequency searching")
            tnum, core, uncore = thread_num, 0, 0
        else:
            tnum, core, uncore = static_search(exe, thread_num)
        print("** Final Result: thread={0}, core={1}, uncore={2} **".format(tnum, core, uncore))
        exit(0)
    if not (thread_only or use_hill or use_grid or use_exaustive):
        use_hill = True
    if use_hill and use_grid:
        print("Error: --hill-climbing and --grid-search could not use simultaneously!")
        sys.exit(1)
    if (use_hill and use_exaustive) or (use_grid and use_exaustive) or (use_hill and use_grid):
        print("Error: Should only configure one of --hill-climbing, --grid-search, --exaustive")
        sys.exit(1)
    if use_hill:
        print("[Info] Use hillclimbing")
    elif use_grid:
        print("[Info] Use Grid searching")
    else:
        print("[Info] Use Exaustive searching")
    keyMap = load_keyMap(keymap_fn)
    if use_thread_search:
        cct = thread_search(exe, keymap_fn, thread_begin, thread_end, thread_step, enable_consistant_thread, enable_continue, target=target)
        if enable_consistant_thread:
            thread_num = cct.thread
        else:
            thread_num = 0
        # cct.thread = 0
        cct.saveTo("thread.cct")
        cct = load_thread_cct("thread.cct")
    else:
        if thread_only:
            print("Thread search will not be applied as thread info has already given: ", cct_src)
            print("[Info] Generate thread cct frequency command without any searching.")
        if freq_command:
            cct = load_thread_cct_freqcommand(freq_command, keymap_fn)
        else:
            cct = load_thread_cct(cct_src)
        if enable_consistant_thread:
            thread_num = cct.child['ROOT'].thread
        else:
            thread_num = 0
    print("[INFO] Thread num=",thread_num)
    if read_only:
        cct.optimize()
        cct.print()
    else:
        if not thread_only:
            if use_hill:
                hill_climbing(exe, cct, keymap_fn, max_iter)
            if use_grid:
                grid_search(exe, cct, keymap_fn, grid_size)
            if use_exaustive:
                exaustive_search(exe, cct, keymap_fn, enable_continue, thread_num=thread_num, target=target)
        generate_cct_frequency_commands(cct, out_fn)
