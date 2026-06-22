from functools import total_ordering
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import RectangleSelector
from types import ModuleType as MT
from .cache import Cache

def search(arr, n):
    if len(arr)==0:
        return -1
    arr = np.asarray(arr)
    idx = np.searchsorted(arr, n)
    if idx == 0:
        return 0
    if idx == len(arr):
        return len(arr) - 1
    if abs(arr[idx] - n) < abs(arr[idx - 1] - n):
        return idx
    return idx - 1


@total_ordering
class Point:
    """
    Holds position + selection state only. Rendering and click-handling
    now live entirely in Interact, which owns ONE shared scatter for all
    points instead of one scatter (and one pick_event connection) per
    Point. See Interact for _on_pick / _sync_colors.
    """

    def __init__(self, x, y):
        self.__x = x
        self.__y = y
        self._deselect()

    @property
    def x(self):
        return self.__x

    @property
    def y(self):
        return self.__y

    def __call__(self):
        return self.x, self.y

    def __repr__(self):
        return f"({self.x}, {self.y})"

    def slope(self, P):
        if isinstance(P, Point):
            try:
                return (P.y - self.y) / (P.x - self.x)
            except ZeroDivisionError:
                return float('inf')
        else:
            raise TypeError(f"{type(P)} object {P} is incompatible to point {self}")

    def __gt__(self, P):
        if isinstance(P, Point):
            return self.x > P.x
        else:
            raise TypeError(f"{type(P)} object {P} is incompatible to point {self}")

    def __eq__(self, P):
        if isinstance(P, Point):
            return self.x == P.x and self.y == P.y
        else:
            raise TypeError(f"{type(P)} object {P} is incompatible to point {self}")

    def _select(self):
        self.__selected = True
        self._col = "red"

    def _deselect(self):
        self.__selected = False
        self._col = "green"

    @property
    def selected(self):
        return self.__selected

    @staticmethod
    def ridge(icol, xs, iP):
        pts = []
        for x in sorted(icol.keys()):
            if len(icol[x]) > 0:
                Px = icol[x]
                y = [i.y for i in Px]
                id = search(y, iP.y)
                if y[id] < iP.y and id < len(icol[x]) - 1:
                    if y[id + 1] - iP.y < (iP.y - y[id]): id += 1
                Px[id]._select()
                iP = Px[id]
                pts.append(iP)

        return Ridge(pts)

    @staticmethod
    def iridge(icol, xs, iP, tol, bias):
        pts = []
        for x in xs:
            if len(icol[x]) > 0:
                Px = icol[x]
                y = [i.y for i in Px]
                id = search(y, iP.y)
                ud = id
                if y[id] < iP.y and id < len(icol[x]) - 1:
                    if y[id + 1] - iP.y < bias * (iP.y - y[id]): ud += 1
                new = True
                if -tol <= iP.slope(Px[ud]) <= tol:
                    iP = Px[ud]
                elif -tol <= iP.slope(Px[id]) <= tol:
                    iP = Px[id]
                else:
                    new = False
                if new:
                    iP._select()
                    pts.append(iP)

        Ridge.update = False

        return Ridge(pts)


class Ridge:
    slc, sgt = None, None
    update = False

    def __init__(self, points: list[Point]):
        self.pts = points

    def __contains__(self, item):
        return item in self.pts

    def __iter__(self):
        return self.pts.__iter__()

    def __len__(self):
        return len(self.pts)

    def __eq__(self,R):
        if type(R) is Ridge and len(R)==len(self):
            return all(i==j for i,j in zip(self,R))
        return False

    def plot(self, ax=plt, dynamic=False):
        Cache.update(self)
        if isinstance(ax, MT):
            fig, ax = plt.subplots()
        if dynamic:
            x = [i.x for i in self.pts]
            y = [i.y for i in self.pts]
            if Ridge.slc: Ridge.slc.remove()
            Ridge.slc, = ax.plot(x, y, c="red", zorder=3)
        else:
            x = [i.x for i in self.pts]
            y = [i.y for i in self.pts]
            Ridge.sgt, = ax.plot(x, y, c="red", zorder=2)

    @staticmethod
    def refresh(pts):
        if not Ridge.update:
            Ridge.update = True
            Ridge.sgt.set_color("green")
            # Ridge.sgt.figure.canvas.draw_idle()
        icol = {}
        for P in pts.selected:
            if P.x in icol:
                icol[P.x].append(P)
            else:
                icol[P.x] = [P]

        X=list(sorted(icol.keys()))

        try:
            Point.ridge(icol, X, icol[X[0]][len(icol[X[0]])//2]).plot(pts._ax, True)
        except IndexError:
            Point.ridge(icol, X, Point(0,2.5)).plot(pts._ax, True)

class Interact:
    """
    Owns ONE shared scatter collection for all points (instead of one
    scatter + one pick_event connection per Point). Selection state still
    lives on each Point; colors are synced to the shared collection in a
    single set_facecolors() call rather than per-point set_color().
    """

    def __init__(self, points: list[Point], ax=plt):
        if isinstance(ax, MT):
            ax = ax.gca()
        self._ax = ax
        self._points = points

        xs = [p.x for p in self._points]
        ys = [p.y for p in self._points]
        colors = [p._col for p in self._points]

        # picker=5 -> hit-test tolerance in points (pixels), rather than
        # the per-marker contains() test you'd get from picker=True. This
        # also makes individual points noticeably easier to click than
        # the old per-point picker=True did.
        self._scatter = ax.scatter(xs, ys, c=colors, zorder=3, picker=5)
        ax.figure.canvas.mpl_connect('pick_event', self._on_pick)

        self._rs = RectangleSelector(
            ax,
            self._on_select,
            useblit=True,
            button=[1],
            minspanx=5, minspany=5,
            spancoords='pixels',
            interactive=False,
        )
        ax.figure.canvas.mpl_connect('button_release_event', self._on_click_empty)

    def _sync_colors(self):
        """Push current per-point colors to the shared collection in one call."""
        colors = [p._col for p in self._points]
        self._scatter.set_facecolors(colors)

    def _on_pick(self, event):
        if event.artist is not self._scatter:
            return
        if len(event.ind) == 0:
            return

        idx = event.ind[0]
        p = self._points[idx]
        if p.selected:
            p._deselect()
        else:
            p._select()

        self._sync_colors()
        Ridge.refresh(self)
        self._ax.figure.canvas.draw_idle()


    def _on_select(self, eclick, erelease):
        x0, x1 = sorted([eclick.xdata, erelease.xdata])
        y0, y1 = sorted([eclick.ydata, erelease.ydata])

        span = abs(x1 - x0) + abs(y1 - y0)
        if span > 1e-10:
            alt = 'alt' in eclick.modifiers
            X = eclick.key in ('X', 'X+', 'x', 'x+', 'alt+x', 'alt+X')

            for p in self._points:
                inside = x0 <= p.x <= x1 and y0 <= p.y <= y1
                if inside and not X:
                    p._select()
                elif not alt and not (inside ^ X):
                    p._deselect()
                elif inside and alt and X:
                    if p.selected:
                        p._deselect()
                    else:
                        p._select()

            self._sync_colors()
            Ridge.refresh(self)

            self._ax.figure.canvas.draw_idle()

    def _on_click_empty(self, event):
        if event.inaxes != self._ax:
            return
        try:
            x0, x1, y0, y1 = self._rs.extents
            span = abs(x1 - x0) + abs(y1 - y0)
        except Exception:
            span = 0

        if span < 1e-10 and not any(abs(event.xdata-p.x)<0.1 and abs(event.ydata-p.y)<0.05 for p in self._points):

            alt = 'alt' in event.modifiers
            X = event.key in ('X', 'X+', 'x', 'x+', 'alt+x', 'alt+X')

            if not (X or alt):
                for p in self._points:
                    p._deselect()

                self._sync_colors()
                Ridge.refresh(self)
    
                self._ax.figure.canvas.draw_idle()

    def force(self,R):
        for p in self._points:
            if p in R:
                p._select()
            else:
                p._deselect()

        self._sync_colors()
        R.refresh(self)
        self._ax.figure.canvas.draw_idle()

    @property
    def selected(self) -> list[Point]:
        return [p for p in self._points if p.selected]

'''from functools import total_ordering
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import RectangleSelector
from types import ModuleType as MT

def search(arr,n):
    arr = np.asarray(arr)
    idx = np.searchsorted(arr, n)
    if idx == 0:
        return 0
    if idx == len(arr):
        return len(arr) - 1
    if abs(arr[idx] - n) < abs(arr[idx - 1] - n):
        return idx
    return idx - 1



@total_ordering
class Point:
    def __init__(self, x, y):
        self.__x = x
        self.__y = y
        self._deselect()

    @property
    def x(self):
        return self.__x

    @property
    def y(self):
        return self.__y

    def __call__(self):
        return self.x, self.y

    def __repr__(self):
        return f"({self.x}, {self.y})"

    def slope(self,P):
        if isinstance(P, Point):
            try:
                return (P.y - self.y) / (P.x - self.x)
            except ZeroDivisionError:
                return float('inf')
        else:
            raise TypeError(f"{type(P)} object {P} is incompatible to point {self}")

    def __gt__(self, P):
        if isinstance(P, Point):
            return self.x > P.x
        else:
            raise TypeError(f"{type(P)} object {P} is incompatible to point {self}")

    def __eq__(self, P):
        if isinstance(P, Point):
            return self.x == P.x and self.y == P.y
        else:
            raise TypeError(f"{type(P)} object {P} is incompatible to point {self}")

    def _select(self):
        self.__selected = True
        self._col="red"

    def _deselect(self):
        self.__selected = False
        self._col="green"

    @property
    def selected(self):
        return self.__selected

    def __click(self,event):
        if event.artist not in (self.__plot):
            return

        if self.selected: self._deselect()
        else: self._select()

        self.__plot.set_color(self._col)

        event.artist.figure.canvas.draw_idle()

    def _refresh(self):
        self.__plot.set_color(self._col)

    def plot(self,ax=plt):
        if isinstance(ax, MT):
            ax = ax.gca()

        self.__plot = ax.scatter(self.x,self.y,c=self._col,zorder=3,picker=True)

        ax.figure.canvas.mpl_connect('pick_event', self.__click)

    @staticmethod
    def ridge(icol,xs,iP):
        pts=[]
        for x in xs:
            if len(icol[x])>0:
                Px=icol[x]
                y = [i.y for i in Px]
                id = search(y, iP.y)
                if y[id]<iP.y and id<len(icol[x])-1:
                    if y[id+1]-iP.y<2*(iP.y-y[id]): id+=1
                Px[id]._select()
                iP=Px[id]
                pts.append(iP)

        return Ridge(pts)
    
    @staticmethod
    def iridge(icol, xs, iP,tol,bias):
        pts = []
        for x in xs:
            if len(icol[x]) > 0:
                Px = icol[x]
                y = [i.y for i in Px]
                id = search(y, iP.y)
                ud=id
                if y[id] < iP.y and id < len(icol[x]) - 1:
                    if y[id + 1] - iP.y < bias * (iP.y - y[id]): ud += 1
                new=True
                if -tol<=iP.slope(Px[ud])<=tol: iP = Px[ud]
                elif -tol<=iP.slope(Px[id])<=tol: iP = Px[id]
                else: new=False
                if new:
                    iP._select()
                    pts.append(iP)

        Ridge.update=False

        return Ridge(pts)



class Ridge:

    slc,sgt=None,None
    update=False

    def __init__(self, points: list[Point]):
        self.pts = points

    def __iter__(self):
        for i in self.pts: yield i

    def plot(self,ax=plt,dynamic=False):
        if isinstance(ax, MT):
            fig = plt.Figure()
            ax = fig.add_subplot(111)
        if dynamic:
            x = [i.x for i in self.pts]
            y = [i.y for i in self.pts]
            if Ridge.slc: Ridge.slc.remove()
            Ridge.slc,=ax.plot(x, y, c="red", zorder=3)
        else:
            x = [i.x for i in self.pts]
            y = [i.y for i in self.pts]
            Ridge.sgt,=ax.plot(x, y, c="red", zorder=2)

    @staticmethod
    def refresh(pts):
        if not Ridge.update:
            Ridge.update=True
            Ridge.sgt.set_color("green")
            #Ridge.sgt.figure.canvas.draw_idle()
        icol = {}
        for P in pts.selected:
            if P.x in icol:
                icol[P.x].append(P)
            else:
                icol[P.x] = [P]

        Point.ridge(icol, list(sorted(icol.keys())), Point(0, 2)).plot(pts._ax,True)


class Interact:

    def __init__(self, points: list[Point], ax=plt):
        if isinstance(ax, MT):
            ax = ax.gca()
        self._ax = ax
        self._points = points

        for p in self._points:
            p.plot(ax)

        self._rs = RectangleSelector(
            ax,
            self._on_select,
            useblit=True,
            button=[1],
            minspanx=5, minspany=5,
            spancoords='pixels',
            interactive=False,
        )
        ax.figure.canvas.mpl_connect('button_release_event', self._on_click_empty)

    def _on_select(self, eclick, erelease):
        x0, x1 = sorted([eclick.xdata, erelease.xdata])
        y0, y1 = sorted([eclick.ydata, erelease.ydata])

        alt = eclick.key in ('alt', 'alt+')

        for p in self._points:
            inside = x0 <= p.x <= x1 and y0 <= p.y <= y1
            if inside:
                p._select()
            elif not alt:
                p._deselect()
            p._refresh()
        Ridge.refresh(self)

        self._ax.figure.canvas.draw_idle()

    def _on_click_empty(self, event):
        if event.inaxes != self._ax:
            return
        try:
            x0, x1, y0, y1 = self._rs.extents
            span = abs(x1 - x0) + abs(y1 - y0)
        except Exception:
            span = 0

        if span < 1e-10:
            for p in self._points:
                p._deselect()
                p._refresh()
            Ridge.refresh(self)

            self._ax.figure.canvas.draw_idle()

    @property
    def selected(self) -> list[Point]:
        return [p for p in self._points if p.selected]
'''