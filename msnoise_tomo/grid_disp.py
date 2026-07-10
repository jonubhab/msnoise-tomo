from msnoise.api import *
from .ANSWT import initModel

from collections import defaultdict

def nested_dict():
    return defaultdict(nested_dict)

def main(filterid,comp,vmin,vmax,show):

    db = connect()

    PER= get_config(db, "ftan_periods", plugin="Tomo")
    periods = np.array([float(pi) for pi in PER.split(',')])

    fmin = float(get_config(db, "ftan_fmin", plugin="Tomo"))
    fmax = float(get_config(db, "ftan_fmax", plugin="Tomo"))
    pmin=1/fmax
    pmax=1/fmin
    if vmin: vgmin=vmin
    else: vgmin = float(get_config(db, "ftan_vgmin", plugin="Tomo"))
    if vmax: vgmax=vmax
    else: vgmax = float(get_config(db, "ftan_vgmax", plugin="Tomo"))

    v_cmap = get_config(db, "v_cmap", plugin="Tomo")
    d_cmap = get_config(db, "d_cmap", plugin="Tomo")

    gridfile = os.path.join("TOMO_FILES", "%02i" % filterid, comp, "Grid.dat")

    answt=os.path.join("ANSWT", "%02i" % filterid, comp)
    save=os.path.join("GRID_DISP", "%02i" % filterid,comp)
    os.makedirs(save, exist_ok=True)

    X, Y, nX, nY, dx, dy = initModel(gridfile)
    print(X,Y,nX, nY, dx, dy)

    vel=nested_dict()

    for per in periods:
        GV = np.loadtxt(os.path.join(answt, "tomo_%.4fs.txt" % per))
        for i in range(int(nX)):
            for j in range(int(nY)):
                vel[X[i][j]][Y[i][j]][per] = GV[i][j]

    for i in range(int(nX)):
        for j in range(int(nY)):
            dcii=[]
            allnan=True
            for per in periods:
                dcii.append(vel[X[i][j]][Y[i][j]][per])
                if not np.isnan(dcii[-1]):
                    allnan = False
            if not allnan:
                fn=os.path.join(save,"DISP","%.4f N - %.4f E .csv"%(Y[i][j],X[i][j]))
                basename=os.path.join(comp,"%.4f N - %.4f E"%(Y[i][j],X[i][j]))
                write_tomo_disp_file(fn,basename,dcii,periods)
                save_FTAN_diag(pmin,pmax,vgmin,vgmax,"%.4f N - %.4f E"%(Y[i][j],X[i][j]),periods,dcii,periods,os.path.join(save,"PLOTS"),show)




def write_tomo_disp_file(fn, basename, dcii,PER):

    df = pd.Series(dcii, index=PER, name="disp")

    if not os.path.isdir(os.path.split(fn)[0]):
        os.makedirs(os.path.split(fn)[0])
    df.to_csv(fn, header=[basename,], float_format='%.4f')

def save_FTAN_diag(xmin,xmax,ymin,ymax,filename, per, disper, PER,save,show=False):
    # This function will plot the FTAN matrix and overlay the dispersion curve
    import matplotlib.pyplot as plt

    print(save,filename)

    # setup matrix for contour plot
    plt.figure()
    # plt.contour(Per, Vitg, amp, 35, colors='k')

    plt.plot(per, disper,'-ok',lw=1.5)
    plt.xlim(xmin, xmax)
    plt.ylim(ymin, ymax)

    # Set axes labels depending on diagramtype
    plt.xlabel("Period (s)")
    plt.ylabel("Velocity (km/s)")

    plt.xticks(PER)

    plt.title("Dispersion Curve\n"+filename)

    os.makedirs(save, exist_ok=True) #
    plt.savefig(os.path.join(save,f"{filename}.png")) #
    if show:
        plt.show()

    plt.close()
