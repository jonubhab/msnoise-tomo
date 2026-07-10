import numpy as np
from .Map import *
from matplotlib.widgets import Button
import os
from .cache import Cache

class idisp:

    def __init__(self,amp,P,V,per,disper,dispers=None):
        self.amp=amp
        self.P=P
        self.V=V
        self.per=per
        self.disper=disper
        self.dispers=[disper] if dispers is None else dispers
        self.picked=False
        Cache.refresh()
        Cache.update(Ridge([Point(x,y) for x, y in zip(per,disper)]))

    def main(self,filename,dist,comp):
        Per, Vitg = np.meshgrid(self.P, self.V)
        fig=plt.Figure()
        ax=fig.add_subplot(111)
        heatmap = ax.contourf(Per, Vitg, self.amp, 35, cmap=inferno)
        fig.colorbar(heatmap, label="Signal Strength")
        ax.plot(self.per, self.disper, '-ok', lw=1.5)
        ax.set_xlim(self.P[0], self.P[-1])
        Cache.lim=max(self.disper.max(),5)
        ax.set_ylim(self.V[0], Cache.lim)
        ax.set_xlabel("Period (s)")
        ax.set_ylabel("Velocity (km/s)")
        NET1, STA1, NET2, STA2, crap = os.path.split(filename)[1].split('_')
        self.name = "%s.%s - %s.%s (%.2f km) %s" % (NET1, STA1, NET2, STA2, dist,comp)
        ax.set_title(self.name)
        return fig

    def pick(self,Xtol,Ytol,mtol,AMPmin,bias,name="2D Heatmap",per=[],disper=[]):
        M = Map(self.amp.T, self.P, self.V, name)
        M.setTol(Xtol,Ytol,mtol,AMPmin,bias)
        M.default(per,disper)
        fig,pts = M.plot(plt)
        self.M = M  # keep around so callers can look up amplitude via idisp.M[point]

        return fig,pts
'''
        icol = {}
        for P in pts.selected:
            if P.x in icol:
                icol[P.x].append(P)
            else:
                icol[P.x] = [P]

        pts = Point.ridge(icol, list(sorted(icol.keys())), Point(0, 2))
        D = np.array([[*i(), M[i]] for i in pts])
        np.savetxt('write_disp.txt', D, header='Period(s) Velocity(km/s) Energy')
'''