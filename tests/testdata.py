import os

TESTDIR = os.path.dirname(os.path.realpath(__file__))

def load_testdata(dataset_name):
    filename = os.path.join(TESTDIR, dataset_name + '.tsv')
    with open(filename, 'rb') as f:
        for line in f:
            if not line:
                continue
            req, resp = line.rstrip(b'\r\n').split(b'\t')
            yield req, resp
