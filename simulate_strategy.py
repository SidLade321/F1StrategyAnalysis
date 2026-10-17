import fastf1
import numpy as np
import matplotlib.pyplot as plt

fastf1.Cache.enable_cache("cache")
session = fastf1.get_session(2022, "Hungary", "R")
session.load()

FUEL_EFFECT = 0.055

lec = session.laps.pick_drivers("LEC").copy()
lec["LapSeconds"] = lec["LapTime"].dt.total_seconds()
clean = lec.pick_wo_box().pick_track_status("1").pick_quicklaps().copy()
TOTAL_LAPS = int(lec["LapNumber"].max())
clean = clean[clean["LapNumber"] < TOTAL_LAPS].copy()
clean["FuelCorrected"] = clean["LapSeconds"] - FUEL_EFFECT * (TOTAL_LAPS - clean["LapNumber"])

# Fit lap time = base + deg * tyre_age for each stint
fits = {}
for stint, g in clean.groupby("Stint"):
    deg, base = np.polyfit(g["TyreLife"], g["FuelCorrected"], 1)
    fits[int(stint)] = {"compound": g["Compound"].iloc[0], "deg": deg, "base": base}
    print(f"Stint {int(stint)} ({fits[int(stint)]['compound']:6}): "
          f"base {base:.2f} s, deg {deg:+.3f} s/lap")

hard = fits[3]      # what Ferrari actually did
medium = fits[2]    # the alternative: fresh mediums

# Simulate a 15-lap stint (laps 40-54) on each tyre
ages = np.arange(1, 16)
hard_laps = hard["base"] + hard["deg"] * ages
medium_laps = medium["base"] + medium["deg"] * ages
gap_per_lap = hard_laps - medium_laps
cumulative = np.cumsum(gap_per_lap)

print(f"\nPredicted 15-lap stint on HARD:   {hard_laps.sum():.2f} s")
print(f"Predicted 15-lap stint on MEDIUM: {medium_laps.sum():.2f} s")
print(f"Time lost by choosing hards:      {cumulative[-1]:+.2f} s")

# Plot
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)

actual = clean[clean["Stint"] == 3]
ax1.scatter(actual["TyreLife"], actual["FuelCorrected"], color="black",
            label="Actual hard laps")
ax1.plot(ages, hard_laps, color="black", linestyle="--", label="Model: hard")
ax1.plot(ages, medium_laps, color="gold", linewidth=2, label="Model: fresh medium")
ax1.set_ylabel("Fuel-corrected lap time (s)")
ax1.set_title("Leclerc, Hungary 2022: what if he'd stayed on mediums?")
ax1.legend()
ax1.grid(alpha=0.3)

ax2.bar(ages, cumulative, color="firebrick")
ax2.set_xlabel("Laps into the stint")
ax2.set_ylabel("Cumulative time lost (s)")
ax2.grid(alpha=0.3, axis="y")

plt.tight_layout()
plt.savefig("figures/strategy_hard_vs_medium.png", dpi=150)
print("Saved figures/strategy_hard_vs_medium.png")
