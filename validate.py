import fastf1
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

fastf1.Cache.enable_cache("cache")
session = fastf1.get_session(2022, "Hungary", "R")
session.load()

FUEL_EFFECT = 0.055
MIN_LAPS = 10        # need enough laps to split into train and test
TRAIN_FRACTION = 0.6

laps = session.laps.copy()
laps["LapSeconds"] = laps["LapTime"].dt.total_seconds()
clean = laps.pick_wo_box().pick_track_status("1").pick_quicklaps().copy()
TOTAL_LAPS = int(laps["LapNumber"].max())
clean = clean[clean["LapNumber"] < TOTAL_LAPS].copy()
clean["FuelCorrected"] = clean["LapSeconds"] - FUEL_EFFECT * (TOTAL_LAPS - clean["LapNumber"])

rows, points = [], []
for (driver, stint), g in clean.groupby(["Driver", "Stint"]):
    g = g.sort_values("LapNumber")
    if len(g) < MIN_LAPS:
        continue
    n_train = int(len(g) * TRAIN_FRACTION)
    train, test = g.iloc[:n_train], g.iloc[n_train:]

    deg, base = np.polyfit(train["TyreLife"], train["FuelCorrected"], 1)
    predicted = base + deg * test["TyreLife"]
    no_wear = train["FuelCorrected"].mean()           # benchmark: tyres don't wear

    err_model = test["FuelCorrected"] - predicted
    err_naive = test["FuelCorrected"] - no_wear
    rows.append({
        "Driver": driver, "Stint": int(stint), "Compound": g["Compound"].iloc[0],
        "TestLaps": len(test),
        "RMSE_model": np.sqrt((err_model ** 2).mean()),
        "RMSE_noWear": np.sqrt((err_naive ** 2).mean()),
    })
    for a, p in zip(test["FuelCorrected"], predicted):
        points.append({"Driver": driver, "Actual": a, "Predicted": p})

res = pd.DataFrame(rows)
pts = pd.DataFrame(points)
pd.set_option("display.float_format", "{:.3f}".format)

print(res.sort_values(["Compound", "RMSE_model"]).to_string(index=False))
print("\nAverage error per compound (s):")
print(res.groupby("Compound")[["RMSE_model", "RMSE_noWear"]].mean())

beats = (res["RMSE_model"] < res["RMSE_noWear"]).mean() * 100
print(f"\nDegradation model beats 'no wear' in {beats:.0f}% of {len(res)} stints")
print(f"Overall: model {res['RMSE_model'].mean():.3f} s vs no-wear {res['RMSE_noWear'].mean():.3f} s")

# Plot: predicted vs actual for every held-out lap
plt.figure(figsize=(6, 6))
plt.scatter(pts["Predicted"], pts["Actual"], alpha=0.4, label="All drivers")
lec = pts[pts["Driver"] == "LEC"]
plt.scatter(lec["Predicted"], lec["Actual"], color="red", label="Leclerc")
lims = [pts[["Predicted", "Actual"]].min().min(), pts[["Predicted", "Actual"]].max().max()]
plt.plot(lims, lims, color="black", linestyle="--", label="Perfect prediction")
plt.xlabel("Predicted lap time (s, fuel-corrected)")
plt.ylabel("Actual lap time (s, fuel-corrected)")
plt.title("Hold-out validation: predicting the last 40% of each stint")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("figures/validation.png", dpi=150)
print("Saved figures/validation.png")
