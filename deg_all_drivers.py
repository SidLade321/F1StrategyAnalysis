import fastf1
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

fastf1.Cache.enable_cache("cache")
session = fastf1.get_session(2022, "Hungary", "R")
session.load()

FUEL_EFFECT = 0.055
MIN_LAPS = 6          # ignore stints too short to fit a line to

laps = session.laps.copy()
laps["LapSeconds"] = laps["LapTime"].dt.total_seconds()
clean = laps.pick_wo_box().pick_track_status("1").pick_quicklaps().copy()

TOTAL_LAPS = int(laps["LapNumber"].max())
clean = clean[clean["LapNumber"] < TOTAL_LAPS].copy()
clean["FuelCorrected"] = clean["LapSeconds"] - FUEL_EFFECT * (TOTAL_LAPS - clean["LapNumber"])

# Fit a line for every driver's every stint
rows = []
for (driver, stint), g in clean.groupby(["Driver", "Stint"]):
    if len(g) < MIN_LAPS:
        continue
    (slope, intercept), cov = np.polyfit(g["TyreLife"], g["FuelCorrected"], 1, cov=True)
    rows.append({
        "Driver": driver,
        "Stint": int(stint),
        "Compound": g["Compound"].iloc[0],
        "Laps": len(g),
        "Deg": slope,
        "Err": np.sqrt(cov[0, 0]),    # uncertainty on the slope (1 standard error)
    })

res = pd.DataFrame(rows)
pd.set_option("display.float_format", "{:.3f}".format)

print("\nEvery stint, sorted by compound:")
print(res.sort_values(["Compound", "Deg"]).to_string(index=False))

print("\nTypical degradation per compound (whole field):")
print(res.groupby("Compound")["Deg"].agg(["median", "count"]))

# Plot: every stint as a dot, Leclerc highlighted
order = ["SOFT", "MEDIUM", "HARD"]
colours = {"SOFT": "red", "MEDIUM": "gold", "HARD": "grey"}
plt.figure(figsize=(8, 5))
rng = np.random.default_rng(0)
for i, comp in enumerate(order):
    sub = res[res["Compound"] == comp]
    others = sub[sub["Driver"] != "LEC"]
    x = i + rng.uniform(-0.15, 0.15, len(others))
    plt.scatter(x, others["Deg"], color=colours[comp], alpha=0.7)
    lec = sub[sub["Driver"] == "LEC"]
    plt.scatter([i] * len(lec), lec["Deg"], color="blue", s=120,
                marker="*", label="Leclerc" if i == 0 else None)

plt.xticks(range(len(order)), order)
plt.axhline(0, color="black", linewidth=0.5)
plt.ylabel("Degradation (s/lap, fuel-corrected)")
plt.title("Hungary 2022: tyre degradation, every driver's stints")
plt.legend()
plt.grid(alpha=0.3, axis="y")
plt.savefig("figures/field_degradation.png", dpi=150)
print("\nSaved figures/field_degradation.png")
