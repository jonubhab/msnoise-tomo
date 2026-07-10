from .Point import *

from .ftan_call import pickgroupdispcurv
from matplotlib.cm import inferno
from msnoise.api import *
from .Map import Map
import shutil
import os
import numpy as np
import pandas as pd
import csv

def main(pair,show,interactive):

    picked="TOMO_DISP"
    src="RAW_FTAN_FILES"

    db = connect()
    PER = get_config(db, "ftan_periods", plugin="Tomo")
    PER = np.array([float(pi) for pi in PER.split(',')])
    params = get_params(db)

    db = connect()
    stations = get_stations(db)
    loc = {f"{s.net}.{s.sta}": s for s in stations}

    filters = get_filters(db)

    freqs = 1 / PER

    print("The requested periods in the TOMOCONFIG are: %s" % PER)
    print("This corresponds to frequencies: %s" % freqs)

    filelist = []
    savefiles = []

    while is_next_job(db, jobtype='TOMO_FTAN') or pair:
        if not pair:
            jobs = get_next_job(db, jobtype='TOMO_FTAN')

            for job in jobs:
                netsta1, netsta2 = job.pair.split(':')
                print(netsta1, netsta2)
                for filter in filters:
                    for comp in ["RW","LW"]:
                        fn = os.path.join(src, "%02i" % filter.ref, "%s_%s_MEAN" % (netsta1.replace('.', '_'), netsta2.replace('.', '_')), comp)
                        if not os.path.exists(os.path.join("DISP CURVE PLOTS", "%02i" % filter.ref, comp,
                                                           "%s - %s.png" % (netsta1, netsta2))):  #
                            if os.path.exists(fn):
                                filelist.append(fn)
                                savefiles.append(os.path.join("DISP CURVE PLOTS", "%02i" % filter.ref, comp))
                            else:
                                print("no folder named", fn)
        else:
            for pi in pair:
                netsta1, netsta2 = pi.split('_')
                for filter in filters:
                    for comp in ["RW", "LW"]:
                        fn = os.path.join(src, "%02i" % filter.ref,
                                          "%s_%s_MEAN" % (netsta1.replace('.', '_'), netsta2.replace('.', '_')), comp)
                        if os.path.exists(fn):
                            filelist.append(fn)
                            savefiles.append(os.path.join("DISP CURVE PLOTS", "%02i" % filter.ref, comp))
                        else:
                            print("no file named", fn)
            break

    print("Will process the following SAC files")
    print(filelist)

    GVdisp = [{}, ] * len(filelist)

    # Prepare for the interpolated dispersion curves
    iper = np.argsort(PER)
    PER = PER[iper]
    Disp = np.zeros((len(PER), len(GVdisp))) * np.nan

    for i, filename in enumerate(filelist):
        # /home/arjun/WESTERN-TIBET/Control/RAW_FTAN_FILES/01/Y2_GARY_Y2_GUGE_MEAN/RW

        NET1, STA1, NET2, STA2, crap = os.path.basename(os.path.dirname(filename)).split('_')
        filter = os.path.basename(os.path.dirname(os.path.dirname(filename)))
        comp = os.path.basename(filename)

        amp = np.loadtxt(os.path.join(filename, "write_amp.txt"))
        P = np.loadtxt(os.path.join(filename, "write_FP.txt"))
        V = np.loadtxt(os.path.join(filename, "write_TV.txt"))
        name = "%s.%s_%s.%s _ %s" % (NET1, STA1, NET2, STA2, comp)
        basename = "%s.%s_%s.%s_%s" % (NET1, STA1, NET2, STA2, crap)

        if comp=="RW":
            seed = loadridge(os.path.join(picked, filter, "ZZ", "%s_%s_%s_%s_%s.csv" % (NET1, STA1, NET2, STA2, crap)))
        elif comp=="LW":
            seed = loadridge(os.path.join(picked, filter, "RW", "%s_%s_%s_%s_%s.csv" % (NET1, STA1, NET2, STA2, crap)))

        meanh = np.sum(seed.y) / len(seed)

        per = P
        dispers = [[], ] * 5
        SNR = Map(amp, P, V)
        scores = [0, ] * 5

        def score(disper):
            s = 0

            for j in range(len(P)):
                x = P[j]
                y = disper[j]
                if not np.isnan(y):
                    PT = Point(x, y)
                    if 0 < j < len(P) - 1:
                        dangle=abs(np.arctan(PT.slope(Point(P[j - 1], disper[j - 1]))) - np.arctan(PT.slope(Point(P[j + 1], disper[j + 1])))) / np.pi
                        c=10
                        blue=lambda x: np.arctan(c*(0.5-x))/(2*np.arctan(c/2))+0.5
                        red=lambda x: 1-x
                        w=lambda x: 1-3*x**2+2*x**3
                        f=lambda x:w(x)*blue(x) + (1-w(x))*red(x)
                        sf = f(dangle) #1 - dangle
                    else:
                        sf = 1
                    s += SNR[x][y] * (P[min(len(P) - 1, j + 1)] - P[max(0, j - 1)]) / 2 * sf * (
                                1 / (1 + np.exp(7.5 * (seed.dist(PT) / meanh - 0.55))))
            return s

        print(f"\nPicking for {filter} _ {name}")

        dispers[0] = viterbi_falling_string_closer(amp.T, P, V, seed, corridor_radius=0.6 * meanh, proximity_weight=0.2)
        scores[0] = score(dispers[0])
        print("Computed using Algorithm 1 \t Score: ", scores[0])
        dispers[1] = optimize_string_fall_fast(amp.T, P, V, seed)
        scores[1] = score(dispers[1])
        print("Computed using Algorithm 2 \t Score: ", scores[1])
        dispers[2] = viterbi_look_ahead(amp.T, P, V, seed)
        scores[2] = score(dispers[2])
        print("Computed using Algorithm 3 \t Score: ", scores[2])

        dispers[3] = viterbi_falling_string(amp.T, P, V, seed, smoothness_penalty=0.5, corridor_radius=0.4  * meanh)
        scores[3] = score(dispers[3])
        print("Computed using Algorithm 4 \t Score: ", scores[3])

        dispers[4] = my_algo(amp, P, V, seed)
        scores[4] = score(dispers[4])
        print("Computed using Algorithm 5 \t Score: ", scores[4])


        best = np.argmax(scores)
        disper = dispers[best]
        print("Chose Algorithm ", best + 1)

        if interactive:
            per = np.atleast_1d(per)
            disper = np.atleast_1d(disper)

            from .Caller import main
            from .idisp_pick import idisp
            iwin = idisp(amp.T, P, V, per, disper, dispers)

            netsta1 = "%s.%s" % (NET1, STA1)
            netsta2 = "%s.%s" % (NET2, STA2)
            dist = gps2dist_azimuth(loc[netsta1].Y, loc[netsta1].X, loc[netsta2].Y, loc[netsta2].X)[0]/1000

            data = {"idisp": iwin,
                    "filename": os.path.join("TOMO_SAC",
                                             "%s_%s_MEAN.sac" % (netsta1.replace('.', '_'), netsta2.replace('.', '_'))),
                    "dist": dist,
                    "comp": comp}
            main(data)

            if iwin.picked:
                # Process the automatically picked dispersion curve from jonubhab's code. Ha! Ha! Ha!
                D = np.loadtxt('write_disp.txt')
                if D.ndim == 2:  # make sure that there is more than one pick
                    isort = np.argsort(D[:, 0])  # sort based on the first column (period)
                    D = D[isort]
                    per = D[:, 0]
                    disper = D[:, 1]
                else:
                    print("Only one dispersion pick...check data!!!")
                    per = D[0]
                    disper = D[1]

        # curve=Ridge(peaks)
        if len(disper) > 0:
            # per=curve.x
            # disper=curve.y

            Disp = interpolate_disp_curve(per, disper, PER)
            write_tomo_disp_file(
                os.path.join(picked, filter, comp, "%s_%s_%s_%s_%s.csv" % (NET1, STA1, NET2, STA2, crap)), basename,Disp, PER)
        else:
            per = []
            disper = []
            print("No dispersion picks within vmin-vmax range")

        save_FTAN_diag(amp, P, V, "%s.%s - %s.%s" % (NET1, STA1, NET2, STA2), basename, per, disper, PER, savefiles[i],
                       show)


def my_algo(amp,P,V,seed):
    SNR = Map(amp, P, V)

    meanh = np.sum(seed.y) / len(seed)


    def maxima(self, x, Xtol=0, Ytol=0, AMPmin=0):
        if Xtol == 0: Xtol = self.Xtol

        if Ytol == 0:
            Ytol = self.Ytol

        if AMPmin == 0:
            AMPmin = self.AMPmin

        def is_ridge(mat):
            c = mat[1][1]
            ld = c > mat[0][0] and c > mat[2][2]
            rd = c > mat[2][0] and c > mat[0][2]

            return ld or rd

        peaks = set()
        A = self.map

        idx = search(self.x, x)
        sx = max(0, min(idx - 1, search(self.x, x - Xtol)))
        ex = min(len(self.x), max(idx + 1, search(self.x, x + Xtol)))
        ampx = A[sx:ex].T

        amp_obj = self[x]
        ampy = amp_obj.map

        y_spacing = self.y[1] - self.y[0] if len(self.y) > 1 else 1
        idy_tol = max(1, int(Ytol / y_spacing))

        trail = False
        for idy in range(len(self.y)):
            if ampy[idy] > AMPmin:
                sy = max(0, idy - idy_tol)
                ey = min(len(self.y), idy + idy_tol + 1)

                if (is_ridge([[A[sx][sy], 0, A[ex - 1][sy]],
                              [0, A[idx][idy], 0],
                              [A[sx][ey - 1], 0, A[ex - 1][ey - 1]]])
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
                else:
                    trail = False
            else:
                trail = False

        return np.array(sorted(peaks))

    peaks = []

    def sf(P3):
        if len(peaks) >= 2:
            P1 = peaks[-2]
            P2 = peaks[-1]

            # Create vectors: incoming track vs candidate step
            v_in = np.array([P2.x - P1.x, P2.y - P1.y])
            v_out = np.array([P3.x - P2.x, P3.y - P2.y])

            # Normalize vectors to calculate true angle cosine
            norm_in = np.linalg.norm(v_in)
            norm_out = np.linalg.norm(v_out)

            if norm_in == 0 or norm_out == 0:
                return 1.0

            # Cosine calculation (-1 to 1)
            cos_theta = np.dot(v_in, v_out) / (norm_in * norm_out)

            # Linear scaling:
            # 0 degrees   -> cos = 1  -> sf = (1+1)/2 = 1.0
            # 90 degrees  -> cos = 0  -> sf = (0+1)/2 = 0.5
            # 180 degrees -> cos = -1 -> sf = (-1+1)/2 = 0.0
            return (cos_theta + 1.0) / 2.0
        else:
            return 1.0

    score = lambda p: SNR[p.x][p.y] * np.exp(-seed.dist(p) ** 2 / (2 * (0.25 * meanh) ** 2)) * sf(p)

    for x in P:
        candy = maxima(SNR, x, 0.2, 0.01, 0.1)
        pts = [Point(x, i) for i in candy]
        if len(pts) > 0:
            iP = pts[0]
            for pt in pts:
                if score(pt) > score(iP):
                    iP = pt
            peaks.append(iP)

    curve=Ridge(peaks)
    per=curve.x
    disper=curve.y
    if len(curve)>0: dcii = np.interp(P, per, disper, left=disper[0], right=disper[-1])
    else: dcii = np.zeros(len(P))*np.nan

    return dcii


def viterbi_falling_string_closer(img_matrix, x_grid, y_grid, seed, smoothness_penalty=2.0, corridor_radius=0.5,
              proximity_weight=1.5):
    """
    img_matrix: 2D array of amplitudes/SNR (rows=Y, cols=X)
    x_grid: 1D array of the map's X coordinates
    y_grid: 1D array of the map's Y coordinates
    seed: Your custom seed object
    proximity_weight: Higher values force it to prefer the ridge closer to the seed
              when multiple ridges exist inside the corridor.
    """
    num_y, num_x = img_matrix.shape
    viterbi_matrix = np.zeros((num_y, num_x))
    backpointer = np.zeros((num_y, num_x), dtype=int)

    # --- STEP 1: COMPUTE LOCAL MAXIMA (THE GROOVES) ---
    # We want to identify where the ridges actually are along each Y column
    is_local_max = np.zeros_like(img_matrix, dtype=bool)
    for x_idx in range(num_x):
        column = img_matrix[:, x_idx]
    # A point is a local maximum if it's greater than or equal to its neighbors
    for y_idx in range(1, num_y - 1):
        if column[y_idx] > column[y_idx - 1] and column[y_idx] > column[y_idx + 1]:
            is_local_max[y_idx, x_idx] = True
    # Handle edges safely
    is_local_max[0, x_idx] = column[0] > column[1]
    is_local_max[-1, x_idx] = column[-1] > column[-2]

    # Initialize the first column (x_grid[0])
    for y_idx in range(num_y):
        p_init = Point(x_grid[0], y_grid[y_idx])
    dist_from_seed = seed.dist(p_init)
    viterbi_matrix[y_idx, 0] = img_matrix[y_idx, 0] - (dist_from_seed ** 2) * 50.0

    # Forward Pass
    for x_idx in range(1, num_x):
        current_map_x = x_grid[x_idx]

    for y_idx in range(num_y):
        current_map_y = y_grid[y_idx]
    current_point = Point(current_map_x, current_map_y)

    # Distance tracking to the seed geometry
    dist_from_seed = seed.dist(current_point)

    # --- THE NEW SCORING RULES ---
    # 1. Corridor Gate
    if dist_from_seed > corridor_radius:
        gate_penalty = -1e6
    else:
        gate_penalty = np.log(corridor_radius / dist_from_seed - 1) / 100

    # 2. Local Maximum Bonus (Rewards being a "valid ridge line")
    # If it's a peak, it gets full amplitude value. If it's not a peak,
    # we heavily suppress it so the string hates sitting on a slope.
    if is_local_max[y_idx, x_idx]:
        ridge_reward = img_matrix[y_idx, x_idx] * 2.0
    else:
        ridge_reward = img_matrix[y_idx, x_idx] * 0.1  # Suppress non-peaks

    # 3. Proximity Bias (Gently penalizes being far from the seed)
    # This breaks ties between two parallel ridges inside the corridor
    proximity_penalty = (dist_from_seed ** 2) * proximity_weight

    # 4. String Stiffness (Transition penalty)
    transition_penalties = ((current_map_y - y_grid) ** 2) * smoothness_penalty

    # Calculate total cumulative score
    candidate_scores = (viterbi_matrix[:, x_idx - 1]
                        + ridge_reward
                        - proximity_penalty
                        - transition_penalties
                        + gate_penalty)

    best_prev_y_idx = np.argmax(candidate_scores)
    viterbi_matrix[y_idx, x_idx] = candidate_scores[best_prev_y_idx]
    backpointer[y_idx, x_idx] = best_prev_y_idx

    # Backtracking Pass
    best_path_indices = np.zeros(num_x, dtype=int)
    best_path_indices[-1] = np.argmax(viterbi_matrix[:, -1])

    for x_idx in range(num_x - 1, 0, -1):
        best_path_indices[x_idx - 1] = backpointer[best_path_indices[x_idx], x_idx]

    return y_grid[best_path_indices]


def optimize_string_fall_fast(img_matrix, x_grid, y_grid, seed, tolerance=1e-4, max_iterations=50000, alpha=0.05,
                  beta=0.05):
    """
    Simulates a continuous string falling simultaneously into the nearest optimal trench.
    Vectorized over the entire X-axis and runs until the curve stabilizes.

    img_matrix: 2D numpy array of amplitudes/SNR (rows=Y, cols=X)
    x_grid: 1D array of the map's X coordinates
    y_grid: 1D array of the map's Y coordinates
    seed: Your custom seed object containing seed.x and seed.y
    tolerance: The threshold for stabilization. If the max movement of any node
       is less than this, it stops iterating.
    max_iterations: A safety cap to prevent infinite loops if it oscillates perfectly.
    alpha: Elastic tension factor (smoothness/stretching resistance)
    beta: External image force factor (gravity pulling it to local maxima)
    """
    num_y, num_x = img_matrix.shape

    # 1. Compute Image Force Gradient along the Y axis across the entire matrix at once
    # This gives us a matrix of slopes pulling the string towards higher amplitudes.
    iy = np.gradient(img_matrix, axis=0)

    # 2. Vectorized Initialization: Interpolate the entire seed on the map's X grid instantly
    current_string_y = np.interp(x_grid, seed.x, seed.y)

    # Pre-calculate Y resolution to normalize forces if needed
    y_min, y_max = y_grid[0], y_grid[-1]

    # 3. Simulation Loop
    for it in range(max_iterations):
        # Map current continuous Y values to their nearest discrete matrix row indices
        # Vectorized implementation of .argmin() for every element in current_string_y
        y_indices = np.abs(y_grid[:, None] - current_string_y).argmin(axis=0)

        # Extract the external gradient forces acting on all points simultaneously
        external_forces = iy[y_indices, np.arange(num_x)]

        # Vectorized Elastic Force: current_string_y[i-1] - 2*y + current_string_y[i+1]
        # We use np.roll to look at left and right neighbors instantly without a loop
        currcopy = np.pad(current_string_y, pad_width=1, mode='edge')
        left_neighbors = np.roll(currcopy, 1)[1:-1]
        right_neighbors = np.roll(currcopy, -1)[1:-1]
        elastic_forces = left_neighbors - 2 * current_string_y + right_neighbors

        # Calculate next step update
        dy = alpha * elastic_forces + beta * external_forces
        new_string_y = np.clip(current_string_y + dy, y_min, y_max)

        # --- STABILIZATION CHECK ---
        # Find the maximum absolute distance any single node moved this step
        max_movement = np.max(np.abs(new_string_y - current_string_y))

        current_string_y = new_string_y

        if max_movement < tolerance:
            print(f"String stabilized beautifully after {it + 1} iterations.")
            break
    else:
        print(f"Reached max iterations ({max_iterations}) before full stabilization.")

    return current_string_y


def viterbi_look_ahead(img_matrix, x_grid, y_grid, seed, smoothness_penalty=1.5, look_ahead_steps=10):
    """
    img_matrix: 2D numpy array of your contour data
    x_grid, y_grid: 1D arrays of the map's grid coordinates
    seed: Your custom seed object
    look_ahead_steps: How many X-steps into the future the algorithm previews to resolve ambiguity
    """
    num_y, num_x = img_matrix.shape
    viterbi_matrix = np.zeros((num_y, num_x))
    backpointer = np.zeros((num_y, num_x), dtype=int)

    # 1. Initialize first column using the seed
    for y_idx in range(num_y):
        p_init = Point(x_grid[0], y_grid[y_idx])
    viterbi_matrix[y_idx, 0] = img_matrix[y_idx, 0] - (seed.dist(p_init) ** 2) * 50.0

    # 2. Forward Pass with Look-Ahead
    for x_idx in range(1, num_x):
        current_map_x = x_grid[x_idx]

    # Determine our look-ahead index safely (don't overshoot the end of the map)
    future_x_idx = min(x_idx + look_ahead_steps, num_x - 1)
    future_map_x = x_grid[future_x_idx]
    actual_look_ahead = future_x_idx - x_idx

    for y_idx in range(num_y):
        current_map_y = y_grid[y_idx]
    current_point = Point(current_map_x, current_map_y)

    # --- THE LOOK-AHEAD MECHANISM ---
    # Instead of looking backward, we estimate where this specific choice
    # would land us in the future if we keep moving along the current ridge trend.
    look_ahead_penalty = 0.0

    if x_idx > 1 and actual_look_ahead > 0:
        # We can't know the exact future points yet, but we can look at the
        # incoming slope from the previous best path to project forward!
        # (Or you can sample the highest local Amp in the future column)

        # Let's check how well the current position itself aligns with the seed
        current_seed_dist = seed.dist(current_point)

        # Project a virtual future point assuming a trend parallel to the seed,
        # or simply evaluate if the current trend is pulling away from the seed.
        look_ahead_penalty = (current_seed_dist ** 2) * 2.0
    else:
        # Default baseline penalty if we are at the very edges
        look_ahead_penalty = (seed.dist(current_point) ** 2) * 2.0

    # Transition penalty (String stiffness/continuity)
    transition_penalties = ((current_map_y - y_grid) ** 2) * smoothness_penalty

    # Total Score: Current Amplitude + Previous Accumulated Score - Penalties
    candidate_scores = (viterbi_matrix[:, x_idx - 1]
                        + img_matrix[y_idx, x_idx]
                        - transition_penalties
                        - look_ahead_penalty)

    best_prev_y_idx = np.argmax(candidate_scores)
    viterbi_matrix[y_idx, x_idx] = candidate_scores[best_prev_y_idx]
    backpointer[y_idx, x_idx] = best_prev_y_idx

    # 3. Backtracking Pass
    best_path_indices = np.zeros(num_x, dtype=int)
    best_path_indices[-1] = np.argmax(viterbi_matrix[:, -1])

    for x_idx in range(num_x - 1, 0, -1):
        best_path_indices[x_idx - 1] = backpointer[best_path_indices[x_idx], x_idx]

    return y_grid[best_path_indices]


def viterbi_falling_string(img_matrix, x_grid, y_grid, seed, smoothness_penalty=1.5, corridor_radius=0.5):
    """
    img_matrix: 2D numpy array of your contour data (rows=Y, cols=X)
    x_grid: 1D array/list of the MAP's exact X coordinates
    y_grid: 1D array/list of the MAP's exact Y coordinates
    seed: Your custom seed object with seed.dist(Point)
    """
    num_y, num_x = img_matrix.shape
    viterbi_matrix = np.zeros((num_y, num_x))
    backpointer = np.zeros((num_y, num_x), dtype=int)

    # 1. Initialize the first column (x_grid[0])
    # We use your custom seed.dist() to anchor the starting edge safely near the seed
    for y_idx in range(num_y):
        p_init = Point(x_grid[0], y_grid[y_idx])
        dist_from_seed = seed.dist(p_init)
        viterbi_matrix[y_idx, 0] = img_matrix[y_idx, 0] - (dist_from_seed ** 2) * 50.0

    # 2. Forward Pass: Traverse along the map's X grid
    for x_idx in range(1, num_x):
        current_map_x = x_grid[x_idx]

        for y_idx in range(num_y):
            current_map_y = y_grid[y_idx]

            # Create your custom Point object for the current candidate
            current_point = Point(current_map_x, current_map_y)

            # --- THE CORRIDOR GATE USING SEED.DIST ---
            # Calculate how far this map point is from the continuous seed line
            dist_from_seed = seed.dist(current_point)

            if dist_from_seed > corridor_radius:
                gate_penalty = -1e6  # Structural wall blocking parallel rival ridges
            else:
                gate_penalty = 0.0  # Entirely free to move inside the trench

            # --- TRANSITION PENALTY (STRING STIFFNESS) ---
            # Measure distance from all potential Y predecessors in the previous X slice
            # To stick strictly to your object methods, we can use P1.dist(P2)
            # or optimize with vector subtraction for speed:
            transition_penalties = ((current_map_y - y_grid) ** 2) * smoothness_penalty

            # Calculate cumulative tracking scores
            candidate_scores = (viterbi_matrix[:, x_idx - 1]
                                + img_matrix[y_idx, x_idx]
                                - transition_penalties
                                + gate_penalty)

            best_prev_y_idx = np.argmax(candidate_scores)
            viterbi_matrix[y_idx, x_idx] = candidate_scores[best_prev_y_idx]
            backpointer[y_idx, x_idx] = best_prev_y_idx

    # 3. Backtracking Pass: Reconstruct the optimal curve from end to start
    best_path_indices = np.zeros(num_x, dtype=int)
    best_path_indices[-1] = np.argmax(viterbi_matrix[:, -1])

    for x_idx in range(num_x - 1, 0, -1):
        best_path_indices[x_idx - 1] = backpointer[best_path_indices[x_idx], x_idx]

    # Return the optimized array of Y values matching the map's x_grid
    return y_grid[best_path_indices]


def interpolate_disp_curve(x, y, PER):
    # This function will write the TOMO_DISP file from the dataframe

    # sort the periods prior to np.interp()
    ix = np.argsort(x)
    x  = x[ix]
    y  = y[ix]

    # Map automatically picked dispersion picks to user requested periods
    dcii = np.interp(PER, x, y, left=np.nan, right=np.nan)
    return dcii


def write_tomo_disp_file(fn, basename, dcii, PER):

    df = pd.Series(dcii, index=PER, name="disp")

    if not os.path.isdir(os.path.split(fn)[0]):
        os.makedirs(os.path.split(fn)[0])
    df.to_csv(fn, header=[basename,], float_format='%.4f')


def save_FTAN_diag(amp,P,U,filename, basename, per, disper, PER,save,show=False):
    # This function will plot the FTAN matrix and overlay the dispersion curve
    import matplotlib.pyplot as plt

    print(save,filename)

    # get FTAN matrix
    amp = amp.T
    xmin = min(P)
    xmax = max(P)
    ymin = min(U)
    ymax = max(U)

    # setup matrix for contour plot
    Per, Vitg = np.meshgrid(P,U)
    plt.figure()
    plt.contourf(Per, Vitg, amp, 35, cmap=inferno)
    plt.colorbar()
    # plt.contour(Per, Vitg, amp, 35, colors='k')

    plt.plot(per, disper,'-or',lw=1.5)
    plt.xlim(xmin, xmax)
    plt.ylim(ymin, ymax)

    # Set axes labels depending on diagramtype
    plt.xlabel("Period (s)")
    plt.ylabel("Velocity (km/s)")

    plt.xticks(PER)

    plt.title("FTAN\n"+filename)

    os.makedirs(save, exist_ok=True) #
    plt.savefig(os.path.join(save,f"{filename}.png")) #
    if show:
        plt.show()

    plt.close()


def loadridge(csvpath) -> Ridge:
    pts=[]
    with open(csvpath,'r') as f:
        reader = csv.reader(f)
        next(reader,None)
        for row in reader:
            if len(row) == 2:
                try:
                    val1 = float(row[0])
                    val2 = float(row[1])
                except ValueError:
                    continue
                pts.append(Point(val1,val2))

        return Ridge(pts)


if __name__ == "__main__":
    main()

