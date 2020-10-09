import argparse
from anytree import Node
from anytree.exporter import DotExporter
from utils.CallingContextTree import CCTFrequencyCommand, CallingContextTree, load_keyMap

def export_node(data, parent):
    return Node(data, parent=parent)

def get_energy(data):
    # print(data.data)
    return float(data.data[-1]) if len(data.data)!=3 else 0.0

def filterWithThreshold(data, threshold):
    # print(threshold)
    return float(data.data[-1]) <= threshold if len(data.data)!=4 else False

def removeEnergy(data):
    data.data = data.data[:-1]
    return data

def main():
    parser = argparse.ArgumentParser(description='Execute scripts to obtain CCT-aware roofline metrics.')
    parser.add_argument('--cct', help='cct file to plot tree figure', default='exaustive.cct')
    parser.add_argument('--out', help='output plot file', default='plot.pdf')
    parser.add_argument('--keymap', help='keymap of cct file', default='PAETT.keymap')
    parser.add_argument('--filter-threshold', help='filter threshold in percentage', type=float, default=0)
    parser.add_argument('--filter-threshold-val', help='filter threshold', type=float, default=100)
    parser.add_argument('--reference-cct', default='thread_metrics/metric.dat.24.27.28')
    args = parser.parse_args()
    cct_ref = None
    with open(args.reference_cct, 'r') as file:
        cct_ref = CallingContextTree.load(file)
        threshold = cct_ref.mergeBy(get_energy) * args.filter_threshold / 100.0
        if args.filter_threshold_val!=0:
            threshold = args.filter_threshold_val
        print("Inited threshold=", threshold)
        cct_ref.filterBy(filterWithThreshold, threshold)
        root = cct_ref.exportTreeWith(export_node)
        # DotExporter(root).to_picture('ref.pdf')
    assert(cct_ref is not None)
    with open(args.cct, 'r') as file:
        cct = CCTFrequencyCommand.load(file, load_keyMap(args.keymap, False))
        # cct_wrapped = cct.getWrapperRoot()
        # with open(args.reference_cct, 'r') as fref:
        #     cct_wrapped.loadAppendedData(fref)
        # threshold = cct.mergeBy(get_energy) * args.filter_threshold / 100.0
        #cct.filterBy(filterWithThreshold, threshold)
        path = ["ROOT", "I:qb.C:435:9", "L:UserInterface.C:137:3", "I:UserInterface.C:210:19", "L:BOSampleStepper.C:451:3"]
        cct.filterByPath( path )
        # cct.processAllDataWith(removeEnergy)
        # print("AAA")
        cct.optimize()
        # cct.filterByTree(cct_ref)
        root = cct.exportTreeWith(export_node)
        # DotExporter(root).to_picture(args.out)
        DotExporter(root).to_dotfile('plot.dot')

if __name__ == '__main__':
    main()