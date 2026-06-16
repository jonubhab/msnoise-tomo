import numpy as np
from .Map import *

def pick(amp,P,V):
    M = Map(amp, P, V)
    M.setTol(0.2,1)
    pts=M.plot(plt)

    icol={}
    for P in pts.selected:
        if P.x in icol: icol[P.x].append(P)
        else: icol[P.x]=[P]

    pts=Point.ridge(icol,list(sorted(icol.keys())),Point(0,2))
    D=np.array([[*i(),M[i]] for i in pts])
    np.savetxt('write_disp.txt',D,header='Period(s) Velocity(km/s) Energy')
