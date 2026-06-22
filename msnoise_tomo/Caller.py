"""
Launches the FTAN ridge-picking GUI from the MSNoise Tomo pipeline.

Blocks on app.mainloop() until the user closes the picker window, then
keeps running with whatever the picker handed back.
"""

import numpy as np
import tkinter as tk
from .Interface import App
from .Point import Point


def main(data):

    captured = {}

    def on_close(result):

        print("App Closed!!")

        captured["result"] = result

        if data["idisp"].picked:
            pts = result["picker"]
            icol = {}
            for P in pts.selected:
                if P.x in icol:
                    icol[P.x].append(P)
                else:
                    icol[P.x] = [P]

            pts = Point.ridge(icol, list(sorted(icol.keys())), Point(0, 2))
            M = data["idisp"].M
            D = np.array([[*i(), M[i]] for i in pts])
            np.savetxt('write_disp.txt', D, header='Period(s) Velocity(km/s) Energy')

    existing_root = tk._default_root
    created_root = existing_root is None
    root = tk.Tk() if created_root else existing_root
    if created_root:
        root.withdraw()  # standalone case: hide the throwaway helper root, only the picker is visible

    app = App(master=root, data=data, on_close=on_close)
    app.wait_window()  # blocks only until THIS window closes, regardless of any other open windows

    if created_root:
        root.destroy()  # clean up only the helper root we made; never touches a pre-existing one

    print("Result captured from the picker:", captured.get("result"))

    # ... continue your pipeline: save picks to DB, move to next
    # station pair, etc.
