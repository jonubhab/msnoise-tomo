"""
Interactive FTAN Ridge-Picking GUI
-----------------------------------
A Tkinter shell with a matplotlib plot on top and a parameter panel +
"Pick" button on the bottom. Clicking "Pick" reads validated parameters,
discards whatever plot is currently shown, and renders a fresh
(interactive) plot built from those parameters.

Designed to be launched FROM another program: pass data in via the
constructor, get a result out via an on_close callback (or by reading
app.result after mainloop() returns).

Replace the two marked functions with your actual plotting code:
    - build_default_plot()      -> the static plot shown on startup
    - build_interactive_plot()  -> your ridge-picking interactive plot
"""

import tkinter as tk
from tkinter import ttk
import pickle
import matplotlib
from matplotlib.backend_bases import key_press_handler, KeyEvent

matplotlib.use("TkAgg")
from .cache import Cache
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import os
import shutil
from pathlib import Path

PARAMS_cache = "DISP CURVE PLOTS/params.pkl"
ICON_CACHE_DIR = os.path.join(Path(__file__).resolve().parent,"img")


# ---------------------------------------------------------------------
# Dark-mode color palettes. Only used when dark mode is actually ON.
# When dark mode is OFF, ttk widgets simply revert to whatever native
# theme the platform was already using, and the matplotlib figures
# fall back to the "light" entries below (standard white/black look).
# ---------------------------------------------------------------------
THEMES = {
    "dark": {
        "bg": "#2b2b2b",
        "fg": "#e0e0e0",
        "button_bg": "#3c3f41",
        "button_active": "#4b4f52",
        "entry_bg": "#3c3f41",
        "entry_fg": "#e0e0e0",
        "text_bg": "#2b2b2b",
        "text_fg": "#e0e0e0",
        "error_fg": "#ff6b6b",
        "fig_bg": "#2b2b2b",
        "ax_bg": "#2b2b2b",
        "ax_fg": "#e0e0e0",
    },
    "light": {
        # Only fig_bg/ax_bg/ax_fg are used (to recolor matplotlib
        # figures back to a standard look). ttk widgets revert to the
        # platform's native theme rather than using this dict.
        "fig_bg": "#ffffff",
        "ax_bg": "#ffffff",
        "ax_fg": "#000000",
    },
}


def _detect_system_dark_mode():
    """Best-effort check of the OS-level dark/light setting.
    Returns False (light) if it can't be determined."""
    import sys
    try:
        if sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0  # 0 = dark, 1 = light
        elif sys.platform == "darwin":
            import subprocess
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True,
            )
            return result.stdout.strip() == "Dark"
        else:  # Linux/other desktops (GNOME-based)
            import subprocess
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True,
            )
            return "dark" in result.stdout.lower()
    except Exception:
        return False

def _invert_named_image(tk_interp, name):
    w = int(tk_interp.call('image', 'width', name))
    h = int(tk_interp.call('image', 'height', name))

    def _rgb(x, y):
        val = tk_interp.call(name, 'get', x, y)
        if isinstance(val, str):
            return tuple(map(int, val.split()))
        return tuple(int(v) for v in val)

    rows = []
    for y in range(h):
        row = " ".join("#%02x%02x%02x" % (255 - r, 255 - g, 255 - b)
                        for r, g, b in (_rgb(x, y) for x in range(w)))
        rows.append("{" + row + "}")

    inverted = tk.PhotoImage(width=w, height=h)
    inverted.put(" ".join(rows))
    for y in range(h):
        for x in range(w):
            if tk_interp.call(name, 'transparency', 'get', x, y):
                inverted.transparency_set(x, y, True)
    return inverted


class ParameterPanel(ttk.Frame):
    """Bottom panel: 4 validated float parameters + Pick button."""

    @staticmethod
    def _load_saved_defaults():
        try:
            with open(PARAMS_cache, "rb") as f:
                return pickle.load(f)
        except (FileNotFoundError, EOFError, pickle.UnpicklingError, OSError):
            return {}  # no cache yet, or it's corrupted -> fall back to hardcoded defaults

    @staticmethod
    def _save_defaults(params):
        try:
            with open(PARAMS_cache, "wb") as f:
                pickle.dump(params, f)
        except OSError:
            pass  # non-fatal: worst case, next run just uses the hardcoded defaults

    def __init__(self, master, on_pick,on_undo,on_redo,on_clean,on_save,on_toggle_theme=None):
        super().__init__(master, padding=(10, 8))
        self.on_pick = on_pick
        self.on_undo = on_undo
        self.on_redo = on_redo
        self.on_clean = on_clean
        self.on_save = on_save
        self.on_toggle_theme = on_toggle_theme

        # (key, label, default, (lo, hi))  -- hi/lo = None means unbounded


        saved = self._load_saved_defaults()
        self.specs = [
            ("Xtol", "X Peak Isolation", saved.get("Xtol", 0.1), (0, None)),
            ("Ytol", "Y Peak Isolation", saved.get("Ytol", 0.01), (0, None)),
            ("mtol", "Slope Tolerance", saved.get("mtol", 1),  (0, None)),
            ("AMPmin", "Minimum SNR", saved.get("AMPmin", 0.25), (0, 1)),
            ("bias", "Positive Slope Bias", saved.get("bias", 2),  (0, None)),
        ]

        btn = [
            ("Pick", self._handle_pick, ["<Return>", "<Control-p>", "<Control-P>"], "[enter]/[Ctrl+P]"),
            ("Undo", self._handle_undo, ["<Control-z>", "<Control-Z>"], "[Ctrl+Z]"),
            ("Redo", self._handle_redo, ["<Control-y>", "<Control-Y>"], "[Ctrl+Y]"),
            ("Clean", self._handle_clean, ["<Control-v>", "<Control-V>", "<Alt-v>", "<Alt-V>"], "[Ctrl+V]/[Alt+V]"),
            ("Save", self.on_save, ["<Control-s>", "<Control-S>"], "[Ctrl+S]"),
            ("Reboot", self._handle_reboot, ["<Control-r>", "<Control-R>"], "[Ctrl+R]")
        ]


        style = ttk.Style()
        # Fallback to a standard light gray if the theme color cannot be read
        bg_color = style.lookup("TFrame", "background") or "#f0f0f0"

        self.log_text = tk.Text(
            self,
            height=5,
            width=65,
            wrap="word",
            bg=bg_color,
            font=("Sans", 10),
            bd=0,
            highlightthickness=0,
        )

        # Remember the original colors so dark mode can be turned back off
        # and the log box returns to exactly how it looked before.
        self._orig_log_bg = self.log_text.cget("bg")
        self._orig_log_fg = self.log_text.cget("fg")

        self.log_text.grid(
            row=0, column=0, rowspan=2, padx=(30, 0), pady=5, sticky="w"
        )

        self._update_text(0)
        self.columnconfigure(0, weight=0)

        self.vars = {}
        for col, (key, label, default, bounds) in enumerate(self.specs,1):
            frame = ttk.Frame(self)
            frame.grid(row=0, column=col, padx=8)

            ttk.Label(frame, text=label).pack(anchor="s")

            var = tk.StringVar(value=str(default))
            entry = ttk.Entry(frame, textvariable=var, width=10)
            entry.pack(anchor="n")
            entry.delete(0, tk.END)
            entry.insert(0, str(default))

            self.vars[key] = var


        for col, (text, func, bindings, label) in enumerate(btn, len(self.specs)+1):

            button = ttk.Button(self, text=text, command=func)
            button.grid(row=0, column=col, padx=(20, 20))

            for key in bindings:
                master.bind_all(key, func)

            lbl = ttk.Label(self, text=label, font=("Sans", 9), foreground="gray")
            lbl.grid(row=1, column=col, padx=(10, 10), sticky="n")

        master.bind_all("<Control-d>",self._handle_toggle_theme)
        master.bind_all("<Control-D>", self._handle_toggle_theme)


        '''
        pick_btn = ttk.Button(self, text="Pick", command=self._handle_pick)
        pick_btn.grid(row=0, column=len(self.specs), padx=(20, 0))
        master.bind_all("<Return>", self._handle_pick)
        master.bind_all("<Control-p>", self._handle_pick)
        master.bind_all("<Control-P>", self._handle_pick)
        psl=ttk.Label(self, text="[enter]/[Ctrl+P]", font=("Sans", 10), foreground="gray")
        psl.grid(row=1, column=len(self.specs), padx=(20, 0), sticky="n")
        '''

        ''''''
        ncol = len(self.specs) + len(btn)
        for col_idx in range(1,ncol+1):
            self.columnconfigure(col_idx, weight=0)

        ''''''

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.grid(row=1, column=1, columnspan=len(self.specs), pady=(6, 0))

    def _update_text(self, i):
        instructions = [
            """Hit Save to proceed with the prepicked dispersion curve.

Click 'Pick' or press ENTER to pick dispersion curve.

Press [Ctrl+D] to toggle appearance theme.
""",
            """Click on the points to select or deselect them.
Drag over the points to select new points.
Alt + Drag to add new points to the existing ridge.
X + Drag to deselect points.
Click any empty region of the canvas to discard all selections.
        """
        ]
        self.log_text.config(state="normal")  # Unlock
        self.log_text.delete("1.0", tk.END)  # Clear contents
        self.log_text.insert(tk.END, instructions[i])  # Write text
        self.log_text.config(state="disabled")

    def _validate(self):
        """Parse + range-check all fields. Returns dict, or None (+ shows error)."""
        values = {}
        for key, label, default, bounds in self.specs:
            raw = self.vars[key].get().strip()
            try:
                val = float(raw)
            except ValueError:
                self.error_label.config(text=f"'{label}' must be a number.")
                return None

            lo, hi = bounds
            if lo is not None and val < lo:
                self.error_label.config(text=f"'{label}' must be >= {lo}.")
                return None
            if hi is not None and val > hi:
                self.error_label.config(text=f"'{label}' must be <= {hi}.")
                return None

            values[key] = val

        self.error_label.config(text="")
        return values

    def _handle_pick(self,event=None):
        params = self._validate()
        if params is not None:
            self._save_defaults(params)
            self.on_pick(params)
            self._update_text(1)

    def _handle_undo(self,event=None):
        sucess=self.on_undo()
        self.error_label.config(text="" if sucess else "Nothing to Undo.")

    def _handle_redo(self,event=None):
        sucess=self.on_redo()
        self.error_label.config(text="" if sucess else "Nothing to Redo.")

    def _handle_clean(self,event=None):
        sucess=self.on_clean()
        self.error_label.config(text="" if sucess else "Not in data picking mode. Click 'Pick' or press ENTER to pick dispersion curve.")

    def _handle_reboot(self,event=None):
        bash_path = shutil.which("bash") or "/bin/bash"
        command_string = "msnoise p tomo reset_ftan && msnoise p tomo ftan"
        exec_args = [bash_path, "-i", "-c", command_string]
        os.execv(bash_path, exec_args)

    def _handle_toggle_theme(self,event=None):
        if self.on_toggle_theme is not None:
            self.on_toggle_theme()

    def apply_theme(self, theme):
        """theme=None reverts this panel's plain-tk widgets to their
        original colors (used when dark mode is switched off)."""
        if theme is None:
            self.log_text.configure(
                bg=self._orig_log_bg, fg=self._orig_log_fg,
                insertbackground=self._orig_log_fg,
            )
            self.error_label.configure(foreground="red")
        else:
            self.log_text.configure(
                bg=theme["text_bg"], fg=theme["text_fg"],
                insertbackground=theme["fg"],
            )
            self.error_label.configure(foreground=theme["error_fg"])


class PlotPanel(ttk.Frame):
    """Top panel: hosts whatever Figure is currently active."""

    def __init__(self, master):
        super().__init__(master)
        self.canvas = None
        self.toolbar = None
        self.figure = None
        # Strong reference to any interactive helper object (e.g. your
        # Ridges/Point picker) so it isn't garbage-collected while shown.
        self.active_picker = None
        # Current color theme applied to any Figure shown here.
        self.theme = THEMES["light"]
        self._toolbar_orig_colors = {} #
        self._toolbar_orig_images = {}
        self._toolbar_dark_images = {}

    def show_figure(self, fig, picker=None):
        """Tear down whatever is currently displayed and embed a new Figure."""
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
        if self.toolbar is not None:
            self.toolbar.destroy()
        if self.figure is not None:
            plt.close(self.figure)

        self.figure = fig
        self.active_picker = picker  # keep alive for the lifetime of this plot

        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas.draw()
        widget = self.canvas.get_tk_widget()
        widget.pack(side="top", fill="both", expand=True)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="bottom", fill="x")

        shortcuts={
            self.toolbar.zoom:["<o>","<O>","<Shift-z>","<Shift-Z>"],
            self.toolbar.pan:["<p>","<P>","<Shift-m>","<Shift-M>"],
            self.toolbar.home:["<h>","<H>","<Shift-h>","<Shift-H>","<Home>"],
            self.toolbar.back:["<Left>"],
            self.toolbar.forward:["<Right>"],
            widget.focus_set:["<backslash>","<bar>","<r>","<R>"]
        }

        for func,keys in shortcuts.items():
            for key in keys:
                widget.bind(key,lambda e,f=func:f())

        # Re-apply whatever theme is currently active so newly-built
        # plots (e.g. after clicking "Pick") match the current mode.
        self._toolbar_orig_colors = {}
        self._style_toolbar()

        self._recolor_current_figure()

    def apply_theme(self, theme):
        self.theme = theme if theme is not None else THEMES["light"]
        self._recolor_current_figure()
        self._style_toolbar()  #

    def _recolor_current_figure(self):
        if self.figure is None:
            return
        fig_bg = self.theme["fig_bg"]
        ax_bg = self.theme["ax_bg"]
        fg = self.theme["ax_fg"]

        self.figure.patch.set_facecolor(fig_bg)
        for ax in self.figure.get_axes():
            ax.set_facecolor(ax_bg)
            ax.tick_params(colors=fg, which="both")
            ax.xaxis.label.set_color(fg)
            ax.yaxis.label.set_color(fg)
            ax.title.set_color(fg)
            for spine in ax.spines.values():
                spine.set_color(fg)
            legend = ax.get_legend()
            if legend is not None:
                legend.get_frame().set_facecolor(fig_bg)
                for text in legend.get_texts():
                    text.set_color(fg)

        if self.canvas is not None:
            self.canvas.draw_idle()

    def _style_toolbar(self):
        if self.toolbar is None:
            return
        dark = self.theme is THEMES["dark"]
        bg = self.theme.get("button_bg") if dark else None
        fg = self.theme.get("fg") if dark else None

        style = ttk.Style()
        default_frame_bg = style.lookup("TFrame", "background") or "#f0f0f0"
        default_label_fg = style.lookup("TLabel", "foreground") or "black"

        for w in [self.toolbar] + list(self.toolbar.winfo_children()):
            widget_type = w.winfo_class()
            is_ttk = widget_type.startswith("T")
            if w not in self._toolbar_orig_colors:
                try:
                    self._toolbar_orig_colors[w] = (w.cget("bg"), w.cget("fg"))
                except tk.TclError:
                    fallback_bg = (
                        default_frame_bg
                        if "Frame" in widget_type
                        else "#f0f0f0"
                    )
                    fallback_fg = default_label_fg
                    self._toolbar_orig_colors[w] = (fallback_bg, fallback_fg)

            orig_bg, orig_fg = self._toolbar_orig_colors[w]

            target_bg = bg if dark else orig_bg
            try:
                if is_ttk:
                    # Clear explicit overrides for clean light mode fallback
                    if not dark:
                        w.configure(background="")
                    else:
                        w.configure(background=target_bg)
                else:
                    w.configure(bg=target_bg)
            except tk.TclError:
                try:
                    w.configure(background=target_bg)
                except tk.TclError:
                    pass

            target_fg = fg if dark else orig_fg
            if target_fg is not None:
                try:
                    if is_ttk:
                        if not dark:
                            w.configure(foreground="")
                        else:
                            w.configure(foreground=target_fg)
                    else:
                        w.configure(fg=target_fg)
                except tk.TclError:
                    try:
                        w.configure(foreground=target_fg)
                    except tk.TclError:
                        pass
            
            image_name = None
            try:
                image_name = w.cget("image")
            except tk.TclError:
                pass
            if image_name:
                if w not in self._toolbar_orig_images:
                    self._toolbar_orig_images[w] = image_name  # just the string
                orig_name = self._toolbar_orig_images[w]
                if dark:
                    if w not in self._toolbar_dark_images:
                        self._toolbar_dark_images[w] = self._get_or_make_dark_icon(w, orig_name)
                    w.configure(image=self._toolbar_dark_images[w])
                else:
                    w.configure(image=orig_name)

    def _get_or_make_dark_icon(self, widget, image_name):
        w = int(widget.tk.call('image', 'width', image_name))
        h = int(widget.tk.call('image', 'height', image_name))
        stable = os.path.basename(str(getattr(widget, "_image_file", None) or image_name))
        key = f"{os.path.splitext(stable)[0]}_{w}x{h}"
        path = os.path.join(ICON_CACHE_DIR, key + ".png")

        if os.path.exists(path):
            try:
                return tk.PhotoImage(file=path)
            except tk.TclError:
                pass

        inverted = _invert_named_image(widget.tk, image_name)
        try:
            os.makedirs(ICON_CACHE_DIR, exist_ok=True)
            inverted.write(path, format="png")
        except (OSError, tk.TclError):
            pass
        return inverted


# ---------------------------------------------------------------------
# Plug your real plotting logic in here. Both now accept `data` -- whatever
# you passed into App(data=...) from the calling program.
# ---------------------------------------------------------------------

def build_default_plot(data=None):
    """Static plot shown on startup. Replace with your initial station-pair view."""

    fig=data["idisp"].main(data["filename"],data["dist"],data["comp"])

    return fig, None


def build_interactive_plot(params, data=None):
    """
    Build the interactive ridge-picking plot from validated parameters.

    params keys: y_tol, slope_tol, min_snr, pos_slope_bias
    data: whatever was passed into App(data=...)

    Must return (fig, picker):
        fig    - the matplotlib Figure to display
        picker - any stateful object holding your interactive callbacks
                 (e.g. a Ridges/Point picker instance), kept alive by
                 PlotPanel. Pass None if you don't need one.
    """
    '''
    fig = Figure(figsize=(8, 4.5), dpi=100)
    ax = fig.add_subplot(111)
    '''

    fig,picker=data["idisp"].pick(params["Xtol"],params["Ytol"],params["mtol"],params["AMPmin"],params["bias"],data["idisp"].name,data["idisp"].per,data["idisp"].disper)
    data["idisp"].picked = True

    return fig, picker


# ---------------------------------------------------------------------


class App(tk.Toplevel):
    def __init__(self, master=None, data=None, on_close=None):
        super().__init__(master)
        self.data = data
        self.on_close_callback = on_close
        self.result = False

        # Dark-mode bookkeeping. Nothing visually changes yet -- the app
        # still starts up looking exactly as it always did, in whatever
        # native ttk theme the platform was already using.
        self.dark_mode = _detect_system_dark_mode()
        self._style = ttk.Style()
        self._original_theme = self._style.theme_use()
        self._original_bg = self.cget("bg")

        self.title("FTAN Ridge Picker")
        self.geometry("1920x1080")

        self.plot_panel = PlotPanel(self)
        self.plot_panel.pack(side="top", fill="both", expand=True)

        self.param_panel = ParameterPanel(self, on_pick=self._on_pick,on_undo=self._on_undo,on_redo=self._on_redo,on_clean=self._on_clean,on_save=self._handle_close,on_toggle_theme=self._toggle_theme)
        self.param_panel.pack(side="bottom", fill="x")

        fig, picker = build_default_plot(self.data)
        self.plot_panel.show_figure(fig, picker)

        if self.dark_mode:
            self._apply_theme(True)

        # Intercept the window manager's close ("X") button. Without this,
        # clicking X just destroys the window with no chance to run anything.
        self.protocol("WM_DELETE_WINDOW", self._kill)

    def _on_pick(self, params):
        fig, picker = build_interactive_plot(params, self.data)
        self.plot_panel.show_figure(fig, picker)
        # Keep the latest params/picker as the running "result" so that
        # whenever the window eventually closes, the most recent pick
        # is what gets handed back.
        self.result = {"params": params, "picker": picker}

    def _on_undo(self):
        R=Cache.undo()
        if R:
            self.result["picker"].force(R)
            return True
        return False

    def _on_redo(self):
        R=Cache.redo()
        if R:
            self.result["picker"].force(R)
            return True
        return False

    def _on_clean(self):
        R=Cache.current
        if R and self.result:
            self.result["picker"].force(R)
            return True
        return False

    def _apply_theme(self, dark):
        """Switch all panels between dark mode and the platform's native
        look. Purely cosmetic -- no app state or behavior is touched."""
        style = self._style

        if dark:
            if style.theme_use() != "clam":
                # 'clam' is the only built-in ttk theme that reliably lets
                # us recolor button/entry backgrounds across platforms.
                style.theme_use("clam")
            theme = THEMES["dark"]
            style.configure("TFrame", background=theme["bg"])
            style.configure("TLabel", background=theme["bg"], foreground=theme["fg"])
            style.configure("TButton", background=theme["button_bg"], foreground=theme["fg"])
            style.map("TButton", background=[("active", theme["button_active"])])
            style.configure("TEntry", fieldbackground=theme["entry_bg"], foreground=theme["entry_fg"])
            self.configure(bg=theme["bg"])
        else:
            # Switching back to the original theme restores that theme's
            # own (untouched) style definitions automatically.
            style.theme_use(self._original_theme)
            theme = None
            self.configure(bg=self._original_bg)

        self.param_panel.apply_theme(theme)
        self.plot_panel.apply_theme(theme)

    def _toggle_theme(self, event=None):
        self.dark_mode = not self.dark_mode
        self._apply_theme(self.dark_mode)

    def _kill(self,event=None):
        bash_path = shutil.which("bash") or "/bin/bash"
        command_string = "msnoise p tomo reset_ftan"
        exec_args = [bash_path, "-i", "-c", command_string]
        os.execv(bash_path, exec_args)

    def _handle_close(self,event=None):
        try:
            if self.on_close_callback is not None:
                self.on_close_callback(self.result)
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            self.destroy()  # <-- always runs now, even if on_close blew up  # <-- this is what makes mainloop() return


if __name__ == "__main__":
    # Standalone test run: no external data, just print on close.
    app = App(data=None, on_close=lambda result: print("Closed with result:", result))
    app.mainloop()
    print("App object still alive after mainloop() returned; result =", app.result)
