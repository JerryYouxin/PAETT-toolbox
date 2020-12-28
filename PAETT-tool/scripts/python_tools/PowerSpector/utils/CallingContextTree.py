from abc import abstractmethod

class CCTLinkedList:
    def __init__(self):
        self.cur_index = 0
        self.curr = None
        self.head = None
        self.tail = None
        self.removed = False

    def current(self):
        return self.curr.data

    def reset(self):
        self.cur_index = 0
        self.curr = self.head
        for p in self.getIterator():
            p.reset()

    # execute func(data) for all elements
    def forAll(self, func):
        p = self.curr
        while p is not None:
            func(p.data)
            p = p.next
    # iterator
    def getIterator(self):
        p = self.head
        while p is not None:
            yield p
            p = p.next

    # insert new node
    def insertNode(self, cct):
        if cct is None:
            return False
        if self.curr is None:
            self.head = cct
        else:
            self.curr.next = cct
        self.curr = cct
        self.tail = cct
        return True

    def remove(self, node):
        if node is None:
            return
        if node.last is not None:
            node.last.next = node.next
        if node.next is not None:
            node.next.last = node.last
        if self.head is node:
            self.head = node.next
        if self.tail is node:
            self.tail = node.last
        self.removed = True

    def moveForward(self):
        if self.removed:
            # if has removed something, disable checking
            if self.curr.next is not None:
                self.curr = self.curr.next
                return True
            return False
        else:
            self.cur_index += 1
            # print(self.curr.name, "MoveForward:", self.cur_index)
            if self.cur_index > self.curr.end_index:
                if self.curr.next is not None:
                    self.curr = self.curr.next
                    # print(self.curr.name, self.cur_index, self.curr.start_index, self.curr.end_index)
                    assert(self.cur_index>=self.curr.start_index)
                    assert(self.cur_index<=self.curr.end_index)
                    return True
        return False

    def getOrInsertNode(self, cctNode):
        # current node failed to move forward, so we try to move to the next node and check again
        if not self.moveForward():
            # failed to move forward, next node must be invalid
            assert(self.curr.next is None)
            # no invalid node, insert new one
            self.insertNode(cctNode)
            return cctNode
        return self.curr

class CallingContextTree:
    def __init__(self, parent=None, name="ROOT", data=None, start_index=0, end_index=-1):
        self.parent = parent
        self.next = None
        self.last = None
        self.name = name
        self.data = data
        self.start_index = start_index
        self.end_index = end_index
        # {'name':<CCTLinkedList>}
        self.child = {}
        self.pruned = False

    def getCCTPath(self):
        if self.parent is None:
            return self.name
        return self.parent.getCCTPath()+';'+self.name

    @staticmethod
    def isSameNode(n1, n2, checkData=False):
        return n1.name==n2.name and n1.start_index==n2.start_index and n1.end_index==n2.end_index

    def getOrInsertChild(self, key, data, start_index=0, end_index=-1):
        assert(end_index==-1 or start_index<=end_index)
        if key not in self.child.keys():
            assert(start_index==0)
            cct = CCTLinkedList()
            cct.insertNode(
                    CallingContextTree(name=key, parent=self, data=data, start_index=start_index, end_index=end_index)
                )
            self.child[key] = cct
        else:
            self.child[key].getOrInsertNode(
                    CallingContextTree(name=key, parent=self, data=data, start_index=start_index, end_index=end_index)
                )
        return self.child[key]

    def insertChild(self, cct):
        key = cct.name
        if key not in self.child.keys():
            ccts = CCTLinkedList()
            ccts.insertNode(cct)
            self.child[key] = ccts
        else:
            self.child[key].getOrInsertNode(cct)
        return self.child[key]

    def reset(self):
        for _, cct in self.child.items():
            cct.reset()

    def processAllDataWith(self, func, args=None):
        if args is None:
            self.data = func(self.data)
        else:
            self.data = func(self.data, args)
        for _, cct in self.child.items():
            cct.reset()
            for n in cct.getIterator():
                n.processAllDataWith(func, args)

    def processAllKeyWith(self, func, args=None):
        if args is None:
            self.name = func(self.name)
        else:
            self.name = func(self.name, args)
        for _, cct in self.child.items():
            cct.reset()
            for n in cct.getIterator():
                n.processAllKeyWith(func, args)

    def optimize(self):
        mayPrune = True
        for _, cct in self.child.items():
            cct.reset()
            for n in cct.getIterator():
                n.optimize()
                mayPrune = mayPrune and n.pruned
        if mayPrune and (self.parent is not None) and self.data==self.parent.data:
        # if self.parent is not None:
        #     print(self.data, self.parent.data)
        #if mayPrune and (self.parent is not None) and self.data.data[0] == self.parent.data.data[0] and self.data.data[1] == self.parent.data.data[1]:
            self.pruned = True
            print("OPT INFO: {0} is pruned".format(self.name))

    # func(<string description of this node>, parent)
    def exportTreeWith(self, func, parent=None):
        desc = self.name + '\n' + str(self.data)
        # print(desc)
        node = func(desc, parent)
        for _, cct in self.child.items():
            cct.reset()
            for n in cct.getIterator():
                n.exportTreeWith(func, node)
        # print(node)
        return node

    def mergeBy(self, func):
        res = func(self.data)
        for _, cct in self.child.items():
            cct.reset()
            for n in cct.getIterator():
                res += n.mergeBy(func)
        return res
    
    def forAll(self, preFunc=None, postFunc=None):
        if preFunc is not None:
            preFunc(self.name, self.start_index, self.end_index, self.data)
        for _, cct in self.child.items():
            cct.reset()
            for n in cct.getIterator():
                n.forAll(preFunc, postFunc)
        if postFunc is not None:
            postFunc(self.name, self.start_index, self.end_index, self.data)
    
    def print(self, pre=""):
        print(pre+'Enter {0} [{1},{2}]:'.format(self.name, self.start_index, self.end_index), end='')
        self.data.print()
        for _, cct in self.child.items():
            for n in cct.getIterator():
                n.print(pre+'  ')
    
    def filterBy(self, filter, args=None):
        may_filter = True
        for _, cct in self.child.items():
            cct.reset()
            for n in cct.getIterator():
                isFiltered = n.filterBy(filter, args)
                if args is None:
                    isFiltered = isFiltered and filter(n.data)
                else:
                    isFiltered = isFiltered and filter(n.data, args)
                if isFiltered:
                    # print("REMOVE:", n)
                    cct.remove(n)
                else:
                    may_filter = False
        return may_filter

    def filterByPath(self, path, depth=1):
        if depth >= len(path):
            return
        for _, cct in self.child.items():
            cct.reset()
            for n in cct.getIterator():    
                if n.name != path[depth]:
                    print("REMOVE:", n.name, path, depth, n.name!=path)
                    cct.remove(n)
                else:
                    n.filterByPath(path, depth+1)

    # only reserves nodes that are in the 'ref'
    def filterByTree(self, ref):
        removedChilds = []
        for key, cct in self.child.items():
            # print(key)
            if key not in ref.child.keys():
                # print("REMOVE CHILD ", key)
                # print("REMOVE INFO: ", self.name, self.start_index, self.end_index)
                # print("REMOVE INFO: ", ref.name, ref.start_index, ref.end_index)
                removedChilds.append(key)
                continue
            cct_ref = ref.child[key]
            cct_ref.reset()
            cct.reset()
            n = cct.head
            if n is not None:
                for n_ref in cct_ref.getIterator():
                    # print("INFO: ", n_ref.name, n_ref.start_index, n_ref.end_index)
                    while n is not None and not CallingContextTree.isSameNode(n, n_ref):
                        # print("REMOVE INFO: ", n.name, n.start_index, n.end_index)
                        # print("REMOVE INFO: ", n_ref.name, n_ref.start_index, n_ref.end_index)
                        cct.remove(n)
                        n = n.next
                    if n is not None:
                        # print("N INFO: ", n.name, n.start_index, n.end_index)
                        n.filterByTree(n_ref)
                        n = n.next
                while n is not None:
                    cct.remove(n)
                    n = n.next
            cct.reset()
        for rc in removedChilds:
            self.child.pop(rc)

    def mergeFrom(self, ref, rule):
        removedChilds = []
        self.data = rule(self.data, ref.data)
        for key, cct in self.child.items():
            if key not in ref.child.keys():
                print("WARNING: REMOVE CHILD ", key)
                print("WARNING: REMOVE INFO: ", self.name, self.start_index, self.end_index)
                print("WARNING: REMOVE INFO(REF): ", ref.name, ref.start_index, ref.end_index)
                removedChilds.append(key)
                continue
            cct_ref = ref.child[key]
            cct_ref.reset()
            cct.reset()
            n = cct.head
            if n is not None:
                for n_ref in cct_ref.getIterator():
                    # print("INFO: ", n_ref.name, n_ref.start_index, n_ref.end_index)
                    while n is not None and not CallingContextTree.isSameNode(n, n_ref):
                        print("WARNING: REMOVE INFO: ", n.name, n.start_index, n.end_index)
                        print("WARNING: REMOVE INFO(REF): ", n_ref.name, n_ref.start_index, n_ref.end_index)
                        cct.remove(n)
                        n = n.next
                    if n is not None:
                        # print("N INFO: ", n.name, n.start_index, n.end_index)
                        n.mergeFrom(n_ref, rule)
                        n = n.next
                while n is not None:
                    print("WARNING: REMOVE INFO: ", n.name, n.start_index, n.end_index)
                    cct.remove(n)
                    n = n.next
            cct.reset()
        for rc in removedChilds:
            self.child.pop(rc)

    def extractDataToList(self, with_cct=True):
        if with_cct:
            data = [ [self.getCCTPath()]+self.data.data ]
        else:
            data = [ self.data.data ]
        for _, cct in self.child.items():
            for n in cct.getIterator():
                data += n.extractDataToList(with_cct)
        return data

    def extractDataByReg(self, res):
        if self.name not in res.keys():
            res[self.name] = [self.data]
        else:
            res[self.name]+= [self.data]
        for _, cct in self.child.items():
            for n in cct.getIterator():
                res[self.name] += n.extractDataToList(False)

    def extractToList(self, enable_cct):
        if enable_cct:
            return self.extractDataToList()
        lst = []
        res = {}
        self.extractDataByReg(res)
        for reg, dlist in res.items():
            length = 0
            for data in dlist:
                length = max(length, len(data))
            metrics = [reg]
            metrics += [ 0 for i in range(0, length) ]
            for data in dlist:
                for i in range(0, len(data)):
                    metrics[i] += data[i]
            lst += metrics
        return lst

    def save(self, file, delimiter=';', pre=''):
        file.write(pre+delimiter.join(['Enter',str(self.name),str(self.start_index),str(self.end_index),'']))
        self.data.save(file)
        for _, cct in self.child.items():
            for n in cct.getIterator():
                n.save(file, delimiter, pre+'  ')
        file.write(pre+"Exit\n")

    @staticmethod
    def load(file):
        root = CallingContextTree()
        line = file.readline()
        cont = line.split(';')
        command = cont[0].strip()
        if command == 'Enter':
            root.name = cont[1]
            root.start_index = int(cont[2])
            root.end_index   = int(cont[3])
            active_thread = int(cont[4])
            root.data = AdditionalData.load(";".join(cont[5:]))
        elif command == 'Exit':
            return None
        else:
            print("Error Unknown command:", command)
            exit(1)
        while True:
            c = CallingContextTree.load(file)
            if c is None:
                break
            c.parent = root
            root.insertChild(c)
        return root
            
class AdditionalData:
    def __init__(self, dataList=[]):
        self.data = dataList

    def save(self, file):
        for d in self.data:
            file.write("{0} ".format(d))
        file.write("\n")

    def __eq__(self, other):
        if len(self.data)!=len(other.data):
            return False
        for i in range(0, len(self.data)):
            if self.data[i]!=other.data[i]:
                return False
        return True

    @staticmethod
    def load(line):
        cont = line.split(' ')
        while cont[-1].strip()=='':
            cont = cont[:-1]
        while cont[0].strip()=='':
            cont = cont[1:]
        data = []
        for c in cont:
            data.append(c)
        p = AdditionalData(data)
        return p
        
    def print(self):
        print(self.data)
    
    def __str__(self):
        return str(self.data)

def load_keyMap(fn, nameIsKey=True):
    keyMap = {"ROOT":-1}
    with open(fn, "r") as f:
        for line in f:
            cont = line[:-1].split(" ")
            key = int(cont[0])
            name= " ".join(cont[1:])
            if nameIsKey:
                keyMap[name] = key
            else:
                keyMap[key] = name
    if nameIsKey:
        keyMap['ROOT'] = -1
    else:
        keyMap[-1] = 'ROOT'
    return keyMap

class CCTFrequencyCommand(CallingContextTree):
    def __generate(self, file, keyMap, pre=""):
        assert(len(self.data.data)==3)
        file.write(pre+'Enter {0} {1} {2} '.format(keyMap[self.name], self.start_index, self.end_index))
        self.data.save(file)
        for _, cct in self.child.items():
            for n in cct.getIterator():
                n.__generate(file, keyMap, pre+"  ")
        file.write(pre+"Exit\n")

    def generate(self, fileName, keymapFn):
        keyMap = load_keyMap(keymapFn)
        with open(fileName, "w") as f:
            self.__generate(f, keyMap)

    @staticmethod
    def load(file, keyMap):
        root = CCTFrequencyCommand()
        line = file.readline()
        # print(line[:-1])
        cont = line.split(' ')
        while cont[0]=='':
            cont = cont[1:]
        command = cont[0].strip()
        if command == 'Enter':
            root.name = keyMap[int(cont[1])]
            #root.name = cont[1]
            root.start_index = int(cont[2])
            root.end_index   = int(cont[3])
            data = [int(cont[4]), int(cont[5]), int(cont[6])]
            root.data = AdditionalData(data)
            # print(root.data)
        elif command == 'Exit':
            return None
        else:
            print("Error Unknown command:", command)
            exit(1)
        while True:
            c = CCTFrequencyCommand.load(file, keyMap)
            if c is None:
                break
            c.parent = root
            root.insertChild(c)
        return root
