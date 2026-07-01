from msnoise.api import *
import os
import sys
import numpy as np
from obspy import read
from obspy.geodetics import gps2dist_azimuth
from sqlalchemy import text

def main():
    db = connect()
    db.execute(text("UPDATE jobs SET flag='T' WHERE jobtype='TOMO_FTAN'"))
    db.commit()
    filters = get_filters(db)
    stations = get_stations(db)
    loc = {f"{s.net}.{s.sta}": s for s in stations}
    comps=["ZZ", "ZN", "ZE", "NZ", "NN", "NE", "EZ", "EN", "EE"]

    while is_next_job(db, jobtype='TOMO_FTAN'):
        jobs = get_next_job(db, jobtype='TOMO_FTAN')

        for job in jobs:
            netsta1, netsta2 = job.pair.split(':')
            print(netsta1, netsta2)

            dist,az,baz=gps2dist_azimuth(loc[netsta1].Y,loc[netsta1].X,loc[netsta2].Y,loc[netsta2].X)
            az = np.deg2rad(az)
            baz= np.deg2rad(baz)

            Q_A=np.array([[1,0,0],
                          [0,np.cos(az),np.sin(az)],
                          [0,-np.sin(az),np.cos(az)]])
            Q_B=np.array([[1,0,0],
                          [0,np.cos(baz),np.sin(baz)],
                          [0,-np.sin(baz),np.cos(baz)]])

            for filter in filters:
                traces, data, sacfound = {}, {}, {}
                for comp in comps:
                    sacfound[comp] = False
                for comp in comps:
                    fn = os.path.join("TOMO_SAC", "%02i" % filter.ref, comp,"%s_%s_MEAN.sac" % (netsta1.replace('.', '_'), netsta2.replace('.', '_')))
                    if os.path.isfile(fn):
                        traces[comp] = read(fn, format="SAC")[0]
                        data[comp]=traces[comp].data
                        sacfound[comp] = True
                    else:
                        print("no file named", fn)
                for comp in comps:
                    if not sacfound[comp]:
                        data[comp]=np.zeros(next((data[c].shape for c in comps if sacfound[c])))
                n = min(len(data[c]) for c in comps)
                for c in comps: data[c] = data[c][:n]

                ZNE=np.array([[data["ZZ"],data["ZN"],data["ZE"]],
                              [data["NZ"],data["NN"],data["NE"]],
                              [data["EZ"],data["EN"],data["EE"]]])

                ZRT = np.einsum('ij,jkt,lk->ilt', Q_A, ZNE, Q_B)
                lvl1z=sacfound["ZN"] and sacfound["ZE"]
                lvl1=sacfound["NZ"] and sacfound["EZ"]
                lvl2=all((sacfound[c] for c in ["EE","NN","EN","NE"]))

                output_data = {
                    "ZZ": ZRT[0][0], "ZR": ZRT[0][1], "ZT": ZRT[0][2],
                    "RZ": ZRT[1][0], "RR": ZRT[1][1], "RT": ZRT[1][2],
                    "TZ": ZRT[2][0], "TR": ZRT[2][1], "TT": ZRT[2][2]
                }

                reliable={
                    "ZZ": False, "ZR": lvl1z, "ZT": lvl1z,
                    "RZ": lvl1, "RR": lvl2, "RT": lvl2,
                    "TZ": lvl1, "TR": lvl2, "TT": lvl2
                }

                for comp_out, data_out in output_data.items():
                    if reliable[comp_out]:
                        out_dir = os.path.join("TOMO_SAC", "%02i" % filter.ref, comp_out)
                        os.makedirs(out_dir, exist_ok=True)

                        tr_out = traces[comp_out if comp_out in traces else "ZZ"].copy()
                        tr_out.data = data_out

                        tr_out.stats.channel = comp_out
                        tr_out.stats.sac.kcmpnm = comp_out

                        tr_out.write(os.path.join(out_dir, "%s_%s_MEAN.sac" % (netsta1.replace('.', '_'), netsta2.replace('.', '_'))), format="SAC")

    db.execute(text("UPDATE jobs SET flag='T' WHERE jobtype='TOMO_FTAN'"))
    db.commit()

if __name__ == "__main__":
    main()