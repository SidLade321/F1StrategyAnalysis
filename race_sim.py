import fastf1
import numpy as np

fastf1.Cache.enable_cache("cache")
session = fastf1.get_session(2022, "Hungary", "R")
session.load()

import sys
FUEL_EFFECT = float(sys.argv[1]) if len(sys.argv) > 1 else 0.055
STINT_START, STINT_END = 40, 54   # Leclerc's hard stint (out-lap 40 to in-lap 54)
MIN_GAP = 0.5                     # how close a blocked car sits behind (s)

laps = session.laps.copy()
laps["T"] = laps["Time"].dt.total_seconds()          # race clock at end of each lap
TOTAL_LAPS = int(laps["LapNumber"].max())

# Table of race time at the end of every lap: rows = lap, columns = driver
times = laps.pivot_table(index="LapNumber", columns="Driver", values="T")
times.index = times.index.astype(int)

# ---- Tyre model for Leclerc (same as simulate_strategy.py) ----
lec_laps = session.laps.pick_drivers("LEC").copy()
lec_laps["LapSeconds"] = lec_laps["LapTime"].dt.total_seconds()
clean = lec_laps.pick_wo_box().pick_track_status("1").pick_quicklaps().copy()
clean = clean[clean["LapNumber"] < TOTAL_LAPS].copy()
clean["FuelCorrected"] = clean["LapSeconds"] - FUEL_EFFECT * (TOTAL_LAPS - clean["LapNumber"])

fits = {}
for stint, g in clean.groupby("Stint"):
    deg, base = np.polyfit(g["TyreLife"], g["FuelCorrected"], 1)
    fits[int(stint)] = (deg, base)

def hard_minus_medium(age):
    """Model: how much slower the hard is than a fresh medium at this tyre age."""
    hard = fits[3][1] + fits[3][0] * age
    medium = fits[2][1] + fits[2][0] * age
    return hard - medium

tyre_age = lec_laps.set_index(lec_laps["LapNumber"].astype(int))["TyreLife"]
lec_real = times["LEC"]
lec_real_lap = lec_real.diff()                        # his real lap times

# ---- The simulator ----
def simulate(threshold, swap_to_mediums):
    t = lec_real.loc[STINT_START - 1]                 # start from his real time at end of lap 39
    for L in range(STINT_START, TOTAL_LAPS + 1):
        free_lap = lec_real_lap.loc[L]
        if swap_to_mediums and STINT_START < L < STINT_END:
            free_lap -= hard_minus_medium(tyre_age.loc[L])
        proposed = t + free_lap

        # Who was directly ahead of Leclerc at the end of the previous lap?
        prev = times.loc[L - 1].drop("LEC").dropna()
        ahead = prev[prev < t]
        if not ahead.empty:
            rival = ahead.idxmax()                    # the closest car ahead
            rival_now = times.loc[L, rival]
            if not np.isnan(rival_now) and proposed < rival_now + MIN_GAP:
                rival_lap = rival_now - times.loc[L - 1, rival]
                advantage = rival_lap - free_lap      # how much faster Leclerc is this lap
                if advantage < threshold:
                    proposed = rival_now + MIN_GAP    # can't pass: stuck behind
        t = proposed
    return t

def finishing_position(final_time):
    others = times.loc[TOTAL_LAPS].drop("LEC").dropna()
    return 1 + int((others < final_time).sum())

real_final = lec_real.loc[TOTAL_LAPS]
print(f"REAL race: P{finishing_position(real_final)}\n")

print(f"{'Pass needs':>10} | {'Baseline sim':>14} | {'Mediums sim':>14} | {'Time gained':>11}")
for threshold in [0.5, 1.0, 1.5, 2.0]:
    base = simulate(threshold, swap_to_mediums=False)
    alt = simulate(threshold, swap_to_mediums=True)
    print(f"{threshold:>8.1f} s | P{finishing_position(base):<2} "
          f"({base - real_final:+6.1f} s) | P{finishing_position(alt):<2} "
          f"({alt - real_final:+6.1f} s) | {base - alt:>+9.1f} s")
