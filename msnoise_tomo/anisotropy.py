import numpy as np
import os
from msnoise.api import *
from matplotlib import pyplot as plt
from scipy import ndimage
from .ANSWT import initModel
import zipfile

kml = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">
<GroundOverlay>
	<name>Anisotropy</name>
	<Icon>
		<href>{path}</href>
		<viewBoundScale>0.75</viewBoundScale>
	</Icon>
	<LatLonBox>
		<north>{lat_north}</north>
		<south>{lat_south}</south>
		<east>{lon_east}</east>
		<west>{lon_west}</west>
	</LatLonBox>
</GroundOverlay>
</kml>
"""


def main(per,filterid,show):

    db = connect()

    if per is None:
        PER= get_config(db, "ftan_periods", plugin="Tomo")
        periods = np.array([float(pi) for pi in PER.split(',')])
    else:
        periods = [float(per),]

    v_cmap = get_config(db, "v_cmap", plugin="Tomo")
    d_cmap = get_config(db, "d_cmap", plugin="Tomo")

    try:
        gridfile = os.path.join("TOMO_FILES", "%02i" % filterid, "RW", "Grid.dat")
    except:
        gridfile = os.path.join("TOMO_FILES", "%02i" % filterid, "LW", "Grid.dat")

    try:
        stacoordfile = os.path.join("TOMO_FILES", "%02i" % filterid, "RW", "STACoord.dat")
    except:
        stacoordfile = os.path.join("TOMO_FILES", "%02i" % filterid, "LW", "STACoord.dat")

    save=os.path.join("ANISOTROPY_FILES", "%02i" % filterid)
    os.makedirs(save, exist_ok=True)

    X, Y, nX, nY, dx, dy = initModel(gridfile)
    STALOC = np.loadtxt(stacoordfile, dtype=str)
    x = np.array(STALOC[:, 3], dtype=float)
    y = np.array(STALOC[:, 2], dtype=float)

    lonlim = [np.amin(X) - dx, np.amax(X) + dx]
    latlim = [np.amin(Y) - dy, np.amax(Y) + dy]

    for PERIOD in periods:
        print("Calculating Anisotropy for Period %.4fs" % PERIOD)

        SH=np.loadtxt(os.path.join("ANSWT","%02i" % filterid,"LW",'tomo_%.4fs.txt'%PERIOD), dtype=float)
        SV = np.loadtxt(os.path.join("ANSWT", "%02i" % filterid, "RW", 'tomo_%.4fs.txt' % PERIOD), dtype=float)

        E=(SH/SV)**2
        np.savetxt(os.path.join(save,'anisotropy_%.4fs.txt' % PERIOD), E)

        fig = plt.figure()
        cf = plt.contourf(X + dx / 2, Y + dy / 2, E, 30, origin='lower',
                          cmap=v_cmap)

        plt.scatter(x, y, marker='^', c='k')
        #plt.contour(X + dx / 2, Y + dy / 2, Dsity, [1, ], colors='w')
        plt.xlim(lonlim[0], lonlim[1])
        plt.ylim(latlim[0], latlim[1])
        plt.axis('off')
        plt.subplots_adjust(left=0, right=1, bottom=0, top=1)
        plt.savefig(os.path.join(save,"test.png"), transparent=True, dpi=600)
        plt.close(fig)

        plt.figure()
        cf = plt.contourf(X + dx / 2, Y + dy / 2, E, 30, origin='lower',
                          cmap=v_cmap)
        plt.scatter(x, y, marker='^', c='k')
        #plt.contour(X + dx / 2, Y + dy / 2, Dsity, [1, ], colors='w')
        cb = plt.colorbar(cf)
        cb.set_label("Group velocity (km/s)")
        plt.ylabel('Latitude')
        plt.xlabel('Longitude')
        plt.title("Anisotropy at Period = %.4f s" %
                  (PERIOD))
        plt.savefig(os.path.join(save,"result_anisotropy_%.4fs.png" % PERIOD), dpi=300)

        with zipfile.ZipFile(os.path.join(save,'anisotropy-result_%.4fs.kmz' % PERIOD), 'w') as z:
            z.writestr('doc.kml', kml.format(
                path='files/test.png',
                lat_north=latlim[1],
                lat_south=latlim[0],
                lon_east=lonlim[1],
                lon_west=lonlim[0],
            ))
            z.write(os.path.join(save,'test.png'), 'files/test.png')
        if show:
            plt.show()
