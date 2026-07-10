import numpy as np
from matplotlib.cm import inferno
from .Point import *



class Map:
    def __init__(self, map, x, y,name=None):
        self.map = map
        self.x = x
        self.y = y
        self.name = name

    def __repr__(self):
        return f"""
        Map Size: {len(self.x)}x{len(self.y)}
        X-Range: {self.x[0]} - {self.x[-1]}
        Y-Range: {self.y[0]} - {self.y[-1]}
        """

    def __getitem__(self, k):
        if isinstance(k, Point): return self.map[search(self.x, k.x)][search(self.y, k.y)]

        if isinstance(k, slice):
            if np.ndim(self.map) != 1:
                if k.step:
                    result = []
                    for i in np.arange(k.start, k.stop, k.step):
                        result.append(self.map[search(self.x, i)])
                    return Map(np.array(result), np.arange(k.start, k.stop, k.step), self.y)
                else:
                    i = search(self.x, k.start)
                    f = search(self.x, k.stop) + 1
                    return Map(self.map[i:f], self.x[i:f], self.y)
            else:
                if k.step:
                    result = []
                    for i in np.arange(k.start, k.stop, k.step):
                        result.append(self.map[search(self.x, i)])
                    return np.array(result)
                else:
                    i = search(self.y, k.start)
                    f = search(self.y, k.stop) + 1
                    return Map(self.map[i:f], self.x, self.y[i:f])

        if np.ndim(self.map) != 1:
            return Map(self.map[search(self.x, k)], np.array([k]), self.y)
        else:
            return self.map[search(self.y, k)]

    def setTol(self,Xtol,Ytol,mtol,AMPmin,bias):
        self.Xtol = Xtol
        self.Ytol = Ytol
        self.mtol = mtol
        self.AMPmin = AMPmin
        self.bias = bias

    def __iter__(self):
        for i in self.map: yield i

    def maxima(self, x,Xtol=0, Ytol=0,AMPmin=0):
        if Xtol ==0: Xtol=self.Xtol

        if Ytol == 0:
            Ytol = self.Ytol

        if AMPmin == 0:
            AMPmin = self.AMPmin

        '''
        ''''''
        x_spacing = self.x[1] - self.x[0] if len(self.x) > 1 else 1
        idx_tol = max(1, int(Xtol / x_spacing))
        idx=search(self.x, x)
        start_bound = max(0, idx - idx_tol)
        end_bound = min(len(self.x), idx + idx_tol + 1)
        ampx=self.map[start_bound:end_bound].T
        ''''''

        amp_obj = self[x]
        amp_data = amp_obj.map

        y_spacing = self.y[1] - self.y[0] if len(self.y) > 1 else 1
        idy_tol = max(1, int(Ytol / y_spacing))

        peaks = set()
        trail=False
        for idy in range(len(self.y)):
            if amp_data[idy] > AMPmin:
                start_bound = max(0, idy - idy_tol)
                end_bound = min(len(self.y), idy + idy_tol + 1)
                if amp_data[idy] == max(amp_data[start_bound:end_bound]): #
                    peaks.add(self.y[idy])
                    ''''''
                    trail=True
                elif amp_data[idy] == max(ampx[idy]):
                    if trail:
                        match = next((x for x in peaks if x in set(self.y[start_bound:end_bound])), None)
                        if match:
                            if amp_data[idy]>self[x][match]:
                                peaks.remove(match)
                                peaks.add(self.y[idy])
                        else:
                            peaks.add(self.y[idy])
                    else:
                        peaks.add(self.y[idy])
                        trail=True
                else: trail=False
            else: trail=False
            ''''''
            '''

        def is_ridge(mat):
            c = mat[1][1]
            ld = c > mat[0][0] and c > mat[2][2]
            rd = c > mat[2][0] and c > mat[0][2]

            return ld or rd

        peaks=set()
        A = self.map

        idx = search(self.x, x)
        sx = max(0, min(idx - 1,search(self.x, x-Xtol)))
        ex = min(len(self.x), max(idx + 1,search(self.x, x+Xtol)))
        ampx=A[sx:ex].T

        amp_obj = self[x]
        ampy = amp_obj.map

        y_spacing = self.y[1] - self.y[0] if len(self.y) > 1 else 1
        idy_tol = max(1, int(Ytol / y_spacing))

        trail = False
        for idy in range(len(self.y)):
            if ampy[idy] > AMPmin:
                sy = max(0, idy - idy_tol)
                ey = min(len(self.y), idy + idy_tol + 1)

                if (is_ridge([[A[sx][sy], 0, A[ex-1][sy]],
                             [0, A[idx][idy], 0],
                             [A[sx][ey-1], 0, A[ex-1][ey-1]]])
                        or ampy[idy] == max(ampy[sy:ey]) or ampy[idy] == max(ampx[idy])):
                    if trail:
                        match = next((x for x in peaks if x in set(self.y[sy:ey])), None)
                        if match:
                            if ampy[idy] > self[x][match]:
                                peaks.remove(match)
                                peaks.add(self.y[idy])
                        else:
                            peaks.add(self.y[idy])
                    else:
                        peaks.add(self.y[idy])
                        trail = True
                else: trail = False
            else: trail = False


        return np.array(sorted(peaks))

    def scan(self):
        peaks={}
        for x in self.x:
            y = self.maxima(x)
            P = [Point(x, i) for i in y]
            #yield x, P
            peaks[x] = P

        for x,ys in self.prepick.items():
            if x in peaks:
                for y in ys:
                    if y not in [p.y for p in peaks[x]]: peaks[x].append(Point(x,y))
            else: peaks[x] = [Point(x,y) for y in ys]

        for x,P in peaks.items():
            yield x, P

    def default(self,per,disper):
        disper=np.atleast_2d(disper)
        self.prepick = {}
        for i,j in enumerate(per):self.prepick[j] = set(disper[:,i])

    def plot(self, ax=plt, show=True):

        if isinstance(ax, MT):
            fig = plt.Figure()
            ax = fig.add_subplot(111)
        else:
            fig = ax.get_figure()

        Per, Vitg = np.meshgrid(self.x, self.y)
        heatmap = ax.contourf(Per, Vitg, self.map.T, 35, cmap=inferno)

        ax.set_xlim(Per.min(), Per.max())
        ax.set_ylim(Vitg.min(), Cache.lim)

        col=[]
        icol={}
        for x,P in self.scan():
            icol[x]=P
            col+=P

        Point.iridge(icol,self.x,Point(0,2.5),self.mtol,self.bias).plot(ax)
        pts=Interact(col,ax)

        fig.colorbar(heatmap, label="Signal Strength")
        ax.set_xlabel("Time Period (s)")
        ax.set_ylabel("Group Velocity (km/s)")
        ax.set_title(self.name)

        fig.tight_layout()

        return fig,pts

