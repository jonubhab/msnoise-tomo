import os
import numpy as np
from msnoise.api import *
from .autopick_sw import loadridge,save_FTAN_diag
from .Point import Ridge
from sqlalchemy import text


def main(comps,show):
    ampfol ="RAW_FTAN_FILES/"
    dispfol="TOMO_DISP/"
    savefol="GROUP_VEL_PLOTS/"


    def get(filter,comp,basename):
        return os.path.join(ampfol, filter,basename, comp),os.path.join(dispfol, filter, comp,basename+".csv"),os.path.join(savefol, filter, comp)

    db = connect()
    db.execute(text("UPDATE jobs SET flag='T' WHERE jobtype='TOMO_FTAN'"))
    db.commit()
    filters = get_filters(db)
    PER = get_config(db, "ftan_periods", plugin="Tomo")
    PER = np.array([float(pi) for pi in PER.split(',')])

    params = get_params(db)
    if not comps: comps = params.components_to_compute


    while is_next_job(db, jobtype='TOMO_FTAN'):
        jobs = get_next_job(db, jobtype='TOMO_FTAN')

        for job in jobs:
            netsta1, netsta2 = job.pair.split(':')
            print(netsta1, netsta2)
            basename = "%s_%s_MEAN" % (netsta1.replace('.', '_'), netsta2.replace('.', '_'))

            for filter in filters:
                for comp in comps:
                    amppath, disppath, savepath = get("%02i" % filter.ref, comp, basename)

                    try:
                        amp = np.loadtxt(os.path.join(amppath, 'write_amp.txt'))
                        U = np.loadtxt(os.path.join(amppath, 'write_TV.txt'))
                        P = np.loadtxt(os.path.join(amppath, 'write_FP.txt'))

                        filename="%s _ %s_%s _ %s"%("%02i" % filter.ref,netsta1,netsta2,comp)

                        curve=loadridge(disppath)
                        per=curve.x
                        disper=curve.y

                        save_FTAN_diag(amp,P,U,filename,basename,per,disper,PER,savepath,show)
                    except FileNotFoundError:
                        print("Inadequate files for ",basename)
