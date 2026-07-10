import glob
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np



def get_ignored_pairs():
    """Reads pairs to ignore from ignore_pairs.txt in the root directory."""
    ignored = set()
    filename = "ignore_pairs.txt"
    if os.path.exists(filename):
        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):  # Allows commenting out lines with '#'
                    ignored.add(line)
    return ignored


if os.path.exists("ignore_pairs.txt"):
    ignored = get_ignored_pairs()


def main(filterid, comp,vmin,vmax):
    alldf = []
    for file in glob.glob('TOMO_DISP/%02i/%s/*' % (filterid, comp)):
        print(file)
        net1,sta1,net2,sta2,crap=os.path.basename(file).split("_")
        tmp = pd.read_csv(file, index_col=0, delimiter=',')
        if "%s.%s:%s.%s"%(net1, sta1, net2, sta2) in ignored: continue
        colname = "%s.%s_%s.%s_MEAN" % (net1, sta1, net2, sta2)
        outside_limits = ~tmp[colname].between(vmin, vmax)
        tmp.loc[outside_limits, colname] = np.nan
        alldf.append(tmp)

    alldf = pd.concat(alldf)

    alldf["mean"] = alldf.mean()
    alldf["median"] = alldf.median()

    alldf.plot(c='k', lw="0.5", legend=False)
    plt.savefig("dispersions-f%02i-%s.pdf" % (filterid, comp))
    plt.show()