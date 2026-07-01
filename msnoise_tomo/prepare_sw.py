from msnoise.api import *
import numpy as np
import shutil
from .lib.libvg_fta import ftan
from sqlalchemy import text

def main():
    db = connect()
    db.execute(text("UPDATE jobs SET flag='T' WHERE jobtype='TOMO_FTAN'"))
    db.commit()
    PER = get_config(db, "ftan_periods", plugin="Tomo")
    PER = np.array([float(pi) for pi in PER.split(',')])
    fmin = float(get_config(db, "ftan_fmin", plugin="Tomo"))
    fmax = float(get_config(db, "ftan_fmax", plugin="Tomo"))
    nfreq = int(get_config(db, "ftan_nfreq", plugin="Tomo"))
    vgmin = float(get_config(db, "ftan_vgmin", plugin="Tomo"))
    vgmax = float(get_config(db, "ftan_vgmax", plugin="Tomo"))

    bmin = float(get_config(db, "ftan_bmin", plugin="Tomo"))
    bmax = float(get_config(db, "ftan_bmax", plugin="Tomo"))

    diagramtype = get_config(db, "ftan_diagramtype", plugin="Tomo")
    ampmin = float(get_config(db, "ftan_ampmin", plugin="Tomo"))
    params = get_params(db)

    filters = get_filters(db)

    freqs = 1 / PER

    while is_next_job(db, jobtype='TOMO_FTAN'):
        savefiles = []
        jobs = get_next_job(db, jobtype='TOMO_FTAN')
        for job in jobs:
            netsta1, netsta2 = job.pair.split(':')
            print(netsta1, netsta2)
            for filter in filters:

                SACfilelist = []
                for comp in ["ZZ", "ZR", "RZ", "RR"]:
                    fn = os.path.join("TOMO_SAC", "%02i" % filter.ref, comp,
                                      "%s_%s_MEAN.sac" % (netsta1.replace('.', '_'), netsta2.replace('.', '_')))
                    print(fn)
                    if os.path.isfile(fn):
                        SACfilelist.append(fn)
                    else:
                        print("no file named", fn)

                amp,ph={},{}
                fn = os.path.join("RAW_FTAN_FILES", "%02i" % filter.ref,
                                                                         "%s_%s_MEAN" % (netsta1.replace('.', '_'),
                                                                                         netsta2.replace('.', '_')),"RW")
                if not os.path.isdir(fn):
                    os.makedirs(fn)
                for i, filename in enumerate(SACfilelist):
                    NET1, STA1, NET2, STA2, crap = os.path.split(filename)[1].split('_')
                    comp=os.path.basename(os.path.dirname(filename))

                    st = read(filename)
                    dist = st[0].stats.sac.dist
                    dt = st[0].stats.delta

                    ftan(filename, fmin, fmax, vgmin, vgmax, bmin, bmax,
                                                           diagramtype, nfreq, ampmin, dist)
                    time.sleep(0.1)

                    F = np.loadtxt('write_FP.txt')  # this is the frequency axis
                    T = np.loadtxt('write_TV.txt')
                    np.savetxt(os.path.join(fn, 'write_FP.txt'), F)
                    np.savetxt(os.path.join(fn, 'write_TV.txt'), T)
                    amp[comp]=np.loadtxt("write_amp.txt")
                    ph[comp] =np.loadtxt("write_ph.txt")
                    #ph[comp]=np.deg2rad(np.loadtxt("write_ph.txt"))

                    basename = "%s_%s_%s_%s_%s" % (NET1, STA1, NET2, STA2, crap)
                    basename = basename.replace(".sac", "")
                    basename = os.path.join("RAW_FTAN_FILES", "%02i" % filter.ref,basename)

                    for _ in ["write_amp.txt",
                              "write_FP.txt",
                              "write_ph.txt",
                              "write_TV.txt",
                              ]:
                        shutil.move(_, _.replace("write", os.path.join(basename,comp)))

                stamp,stph=stack(amp,ph)

                np.savetxt(os.path.join(fn,'write_amp.txt'), stamp)
                np.savetxt(os.path.join(fn, 'write_ph.txt'), stph)


                comp="TT"
                fn = os.path.join("TOMO_SAC", "%02i" % filter.ref, comp,
                                    "%s_%s_MEAN.sac" % (netsta1.replace('.', '_'), netsta2.replace('.', '_')))
                print(fn)
                if os.path.isfile(fn):
                    SACfilelist.append(fn)
                else:
                    print("no file named", fn)


                fn = os.path.join("RAW_FTAN_FILES", "%02i" % filter.ref,
                                                                         "%s_%s_MEAN" % (netsta1.replace('.', '_'),
                                                                                         netsta2.replace('.', '_')),"LW")
                if not os.path.isdir(fn):
                    os.makedirs(fn)
                for i, filename in enumerate(SACfilelist):
                    NET1, STA1, NET2, STA2, crap = os.path.split(filename)[1].split('_')
                    comp=os.path.basename(os.path.dirname(filename))

                    st = read(filename)
                    dist = st[0].stats.sac.dist
                    dt = st[0].stats.delta

                    ftan(filename, fmin, fmax, vgmin, vgmax, bmin, bmax,
                                                           diagramtype, nfreq, ampmin, dist)
                    time.sleep(0.1)

                    for _ in ["write_amp.txt",
                              "write_FP.txt",
                              "write_ph.txt",
                              "write_TV.txt",
                              ]:
                        shutil.move(_, os.path.join(fn,_))


    db.execute(text("UPDATE jobs SET flag='T' WHERE jobtype='TOMO_FTAN'"))
    db.commit()



                #savefiles.append(os.path.join("TOMO_SAC", "%02i" % filter.ref, "RW"))

def stack(amp, ph, normalize=True):
    """
    Coherently stack ZZ, RR, ZR, RZ FTAN matrices into a single
    high-SNR composite Rayleigh-wave FTAN matrix, following
    G_LR0 = G_ZZ + G_RR + IFFT(G_RZ*e^{+i pi/2} + G_ZR*e^{-i pi/2})

    Parameters
    ----------
    amp : dict of 2D np.ndarray, keys "ZZ","RR","ZR","RZ"
        FTAN amplitude matrices, shape (len(GV), len(T))
    ph : dict of 2D np.ndarray, same keys/shape
        FTAN phase matrices (radians)
    GV : 1D np.ndarray
        Group velocity axis
    T : 1D np.ndarray
        Period axis
    normalize : bool
        If True, divide summed amplitude by 4 (number of stacked
        components) to keep amplitude scale comparable to a
        single component.

    Returns
    -------
    amp_stack, ph_stack : 2D np.ndarray
        Amplitude and phase of the composite Rayleigh FTAN matrix
    """

    # Reconstruct analytic signal (complex) for each component
    Z_zz = amp["ZZ"] * np.exp(1j * ph["ZZ"])
    Z_rr = amp["RR"] * np.exp(1j * ph["RR"])

    # Apply the quadrature phase correction to the cross terms
    Z_rz = amp["RZ"] * np.exp(1j * (ph["RZ"] + np.pi / 2))
    Z_zr = amp["ZR"] * np.exp(1j * (ph["ZR"] - np.pi / 2))

    # Coherent sum
    Z_stack = Z_zz + Z_rr + Z_rz + Z_zr

    if normalize:
        Z_stack /= 4.0

    amp_stack = np.abs(Z_stack)
    ph_stack = np.angle(Z_stack)
    ph_stack = np.unwrap(ph_stack, axis=1)

    return amp_stack, ph_stack
