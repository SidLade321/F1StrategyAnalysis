import fastf1
import numpy as np
import matplotlib.pyplot as plt

fastf1.Cache.enable_cache("cache")
session = fastf1.get_session(2022, "Hungary", "R")
session.load()

lec = session.laps.pick_drivers("LEC").copy()
lec["LapSeconds"] = lec["LapTime"].dt.total_seconds()
clean = lec.pick_wo_box().pick_track_status("1").pick_quicklaps().copy()

TOTAL_LAPS = int(lec["LapNumber"].max())
clean = clean[clean["LapNumber"] < TOTAL_LAPS].copy()        # drop the cruise-in last lap

# --- Stage 3: fuel correction ---
FUEL_EFFECT = 0.055   # seconds gained per lap from burning fuel (ASSUMPTION, we test this later)
laps_of_fuel_left = TOTAL_LAPS - clean["LapNumber"]
clean["FuelCorrected"] = clean["LapSeconds"] - FUEL_EFFECT * laps_of_fuel_left
# = "what would this lap time be with an empty tank?", so every lap is compared fairly

# --- Stage 4: fit a straight line per stint: lap time vs tyre age ---
colours = {"SOFT": "red", "MEDIUM": "gold", "HARD": "black"}
plt.figure(figsize=(10, 5))

for stint, group in clean.groupby("Stint"):
    compound = group["Compound"].iloc[0]
    x = group["TyreLife"]
    y = group["FuelCorrected"]
    slope, intercept = np.polyfit(x, y, 1)            # slope = degradation in s/lap
    print(f"Stint {int(stint)} ({compound:6}): {slope:+.3f} s/lap, "
          f"{len(group)} laps")

    plt.scatter(x, y, color=colours[compound], label=f"Stint {int(stint)} {compound}")
    xs = np.linspace(x.min(), x.max(), 10)
    plt.plot(xs, slope * xs + intercept, color=colours[compound], linestyle="--")

plt.xlabel("Tyre age (laps)")
plt.ylabel("Fuel-corrected lap time (s)")
plt.title(f"Leclerc, Hungary 2022: tyre degradation (fuel effect {FUEL_EFFECT} s/lap)")
plt.legend()
plt.grid(alpha=0.3)
plt.savefig("figures/lec_degradation.png", dpi=150)
print("Saved figures/lec_degradation.png")
