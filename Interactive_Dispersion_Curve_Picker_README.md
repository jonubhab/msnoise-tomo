# Interactive FTAN Ridge Picker
 
This adds an interactive picking step on top of MSNoise Tomo's FTAN stage. It doesn't replace anything in the existing pipeline — it sits between the C++ FTAN computation and the file it normally writes (`write_disp.txt`), letting you see and correct what gets picked before it's handed off to `TOMO_DISP`.
 
## The problem this solves
 
If you've run the stock FTAN step on a real dataset, you've probably hit some combination of these:
 
- The dispersion curve `vg_fta.so` hands back often isn't trustworthy. It jumps between unrelated peaks in the FTAN diagram and the resulting curve gets discontinuous in several places, with no way to see *why* it picked what it picked.
- There was no real way to intervene — IFTAN exists, but driving it to fix a single bad pick is more confusing than it should be.
- FTAN flags every job as done as soon as a batch starts. If a run gets interrupted or crashes partway through, the jobs already *look* finished to MSNoise, so you can't just resume — you have to manually sort out which pairs actually have a usable result.
- After running FTAN repeatedly in the same session, the program eventually stops being able to load new contour plots at all.
## What this adds
 
- A peak-detection pass over the full group-velocity-vs-period (or frequency) SNR field for each pair, which finds every local maximum and stitches together the most continuous dispersion curve it can from them.
- That algorithm-picked curve overrides whatever the raw FTAN binary would have used on its own, and instead of trusting it blindly, it's shown to you on a plot so you can accept or correct it.
- Every candidate peak is plotted as a clickable point. You build your own curve by selecting points with the mouse; your selection is drawn in red, and the algorithm's own continuous guess is drawn in green underneath it for reference.
- The picking parameters (described below) are exposed in a panel so you can tune them per pair, and your last-used values are cached to disk so you don't have to retype them for every single pair in a batch.
- Undo/redo/clean controls so a bad rectangle-select or a stray misclick doesn't cost you the whole pair.
- A `reset_ftan` command that lets you safely resume an interrupted batch, or — if you really need to — wipe everything and start clean.
- A "Reboot" shortcut for the specific failure mode where FTAN stops being able to render new plots after running for a while: it terminates, resets the affected job(s), and restarts `msnoise p tomo ftan` for you.
The final curve, once you save it, is rendered to a `.png` for your records and `write_disp.txt` is overwritten with your picks — from there, the existing MSNoise code relocates it into `TOMO_DISP/` exactly as before.
 
## How the picking algorithm works
 
For each period (or frequency) column in the FTAN amplitude diagram, the algorithm looks for local maxima in velocity, filtering out anything below a noise floor and merging maxima that are too close together to be meaningfully distinct. It then walks across columns, trying to connect one maximum per column into a single continuous ridge, rejecting connections that would require an implausibly large jump in velocity from one column to the next.
 
The five parameters below control exactly how forgiving each of those steps is. Defaults are a reasonable starting point, but the right values genuinely depend on your data — frequency content, noise level, and station spacing all affect how clean the FTAN diagram looks. Expect to nudge them a little on your first few pairs. Once you land on values that work for your dataset, you won't have to re-enter them: the panel remembers your last-used values and reloads them automatically the next time the window opens.
 
| Parameter | Label in the GUI | What it controls |
|---|---|---|
| `Xtol` | X Peak Isolation | Minimum separation, along the period/frequency axis, for two candidate peaks to count as distinct. Anything closer together is merged into one (the stronger peak wins). |
| `Ytol` | Y Peak Isolation | The same idea, but along the velocity axis. |
| `AMPmin` | Minimum SNR | Noise floor. Points in the FTAN diagram below this amplitude are never considered candidate peaks at all. |
| `mtol` | Slope Tolerance | The steepest allowed jump in velocity between two consecutive picks. If connecting the next candidate would exceed this, the ridge breaks there instead of jumping to an unrelated peak. |
| `bias` | Positive Slope Bias | When there's a tie between two nearby candidates for the next point on the ridge, this biases the choice toward the one with higher velocity — i.e. toward a positive slope, which is the more common shape for a real dispersion curve. |
 
Both `Xtol` and `Ytol` are in the same units as whatever's on the plot's axes (so typically seconds and km/s, but this follows your diagram type).
 
## Selecting points with the mouse
 
Once you click **Pick**, every candidate peak appears as a point on the contour plot and you're in selection mode:
 
| Action | Effect |
|---|---|
| Click a single point | Toggle that point's selection on/off |
| Click-and-drag a box | Select everything inside the box, deselect everything outside it |
| **Alt** + drag a box | Add the points inside the box to your current selection, without touching anything else |
| **X** (hold) + drag a box | Deselect only the points inside the box |
| **Alt** + **X** + drag a box | Toggle (flip) the selection of just the points inside the box |
| Click an empty part of the canvas | Deselect everything |
 
Your live selection is drawn in red; the algorithm's own reference curve stays green underneath it so you can always compare the two.
 
## The Toolbar
 
**Pick** — Runs the peak-detection algorithm with whatever parameter values are currently in the panel, and switches you into selection mode. Use it when:
- You don't like the pre-selected (green) curve and want to build your own from the candidate points, or
- You've just changed one of the five parameters and want to see how the set of candidate maxima changes before you commit to a selection.

**Undo** — Steps back to your previous selection state. Use it to recover from a misclick, or to back out of a selection that turned out worse than the one you had before.
 
**Redo** — Steps forward again. Paired with Undo, this lets you flip back and forth between two candidate ridges to compare them before deciding which one to keep.
 
**Clean** — Deselects any points you've picked that aren't actually part of the connected ridge — stray clicks, accidental extra selections, that sort of thing. Under the hood it doesn't go scanning for which points are "stray"; it just reloads the cached state of the current ridge, since that's already sitting in memory.
 
**Save** — Commits your current selection (or the original algorithm curve, if you never clicked Pick at all) as the final dispersion curve for this pair, writes it out, and closes the window so the pipeline can move on. If the default curve already looked fine to you, you can skip picking entirely and just hit Save.
 
**Reboot** — For when FTAN has stopped being able to load new contour plots after running for a while in the same session: this terminates the current process, resets the affected job(s), and restarts `msnoise p tomo ftan` automatically so you don't have to do it by hand.
 
### The matplotlib navigation toolbar
 
**Zoom** — Enlarges a region of the plot. Useful when a stretch of the FTAN diagram has a dense cluster of candidate points and you need more room to click the right one.
 
**Pan** — Shifts the view without changing the zoom level. Most of the time this is just for moving around a zoomed-in region, but it has one more niche use: points sitting right at the edge of the plot sometimes don't register clicks or fall inside a drag box properly. Panning the view so that point is no longer at the very edge usually fixes it.
 
**Home** — Resets the view back to the original, full extent.
 
### Closing the window
 
Closing the window with the operating system's own **X / close button** is deliberately different from Save: instead of writing anything out, it safely terminates the process and resets the job for that pair, so MSNoise sees it as not-yet-done rather than wrongly marked complete. This means `msnoise p tomo ftan` will pick that pair back up cleanly the next time you run it — but it also means closing this way does **not** save whatever you'd selected. Use Save when you want to keep a pick; use the close button when you want to bail out of the current pair without keeping anything.
 
## Dark mode
 
The picker checks your OS's light/dark setting on startup and matches it automatically, falling back to light mode if it can't tell. You can flip it manually at any point with the dark-mode shortcut below — this recolors the plot, the panel, and the toolbar icons together.
 
## Keyboard shortcuts
 
| Key(s) | Action |
|---|---|
| Enter, Ctrl+P | Pick |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+V, Alt+V | Clean |
| Ctrl+S | Save |
| Ctrl+R | Reboot |
| Ctrl+D | Toggle dark mode |
| o, Shift+Z | Toolbar: Zoom *(plot must have focus)* |
| p, Shift+M | Toolbar: Pan *(plot must have focus)* |
| h, Shift+H, Home | Toolbar: Home/reset view *(plot must have focus)* |
| ← | Back to previous view *(plot must have focus)* |
| → | Forward to next view *(plot must have focus)* |
| \\, \|, r | Return focus to the plot canvas |
 
The plot-navigation shortcuts only fire while the plot itself has focus — click on the plot once if they don't seem to respond.
 
## Resuming or resetting a run
 
```
msnoise p tomo reset_ftan
```
Resets the job flags for the FTAN stage without deleting anything on disk. Combined with the fact that a pair already has a saved plot is treated as "done" and skipped automatically, this is the safe way to resume after an interruption — finished pairs stay finished, unfinished ones get picked back up.
 
```
msnoise p tomo reset_ftan --all
```
A full wipe: deletes every saved plot and resets every job. Since this throws away all picking progress and can't be undone, it asks you to type `DELETE PROGRESS` to confirm before doing anything.
 
## Output files
 
| File / folder | Contents |
|---|---|
| `DISP CURVE PLOTS/<filter>/<comp>/<STA1> - <STA2>.png` | The rendered review plot for the pair — also doubles as the marker that tells a future run this pair is already done |
| `DISP CURVE PLOTS/params.pkl` | Your last-used picking parameters |
| `write_disp.txt` | The final (Period, Velocity, Energy) picks for the current pair, picked up from there by the existing MSNoise code and relocated into `TOMO_DISP/` |
 
