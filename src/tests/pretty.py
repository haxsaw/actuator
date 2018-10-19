__author__ = 'tom'

import sys
import pprint as pp
import json


def formatit(fname):
    d = json.loads(open(fname, "r").read())
    print("d has %d items" % len(d["CATALOG"]))
    oname = ".".join([fname.split(".")[0], "txt"])
    f = open(oname, "w")
    pp.pprint(d, stream=f)
    f.close()
    return d


if __name__ == "__main__":
    d = formatit(sys.argv[1])
