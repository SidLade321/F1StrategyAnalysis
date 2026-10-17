import fastf1
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

fastf1.Cache.enable_cache("cache")

FUEL_EFFECT = 0.055   # s/lap
MIN_LAPS = 10         # only test stints with at least this many clean laps
TRAIN_FRAC = 0.6      # fit on first 60%, predict the last 40%

session = fastf1.get_session(2022, "Hungary", "R")
session.load(telemetry=False, weather=False, messages=False)
laps = session.laps
TOTAL_LAPS = int(laps["LapNumber"].max())

# Same cleaning + fuel correction as the rest of the project
clean = laps.pick_wo_box().pick_track_status("1").pick_quicklaps().copy()
clean = clean[clean["LapNumber"] < TOTAL_LAPS].copy()
clean["LapSeconds"] = clean["LapTime"].dt.total_seconds()
clean["FuelCorrected"] = clean["LapSeconds"] - FUEL_EFFECT * (TOTAL_LAPS - clean["LapNumber"])


# ---------------- Models (each returns: prediction function, number of parameters) ----------------
def fit_none(x, y):
    m = y.mean()
    return (lambda t: np.full(np.shape(t), m)), 1


def fit_linear(x, y):
    c = np.polyfit(x, y, 1)
    return (lambda t: np.polyval(c, t)), 2


def fit_quadratic(x, y):
    c = np.polyfit(x, y, 2)
    return (lambda t: np.polyval(c, t)), 3


def fit_cliff(x, y):
    """Two straight lines joined at a breakpoint lap k (k found by trying every option)."""
    best = None
    for k in np.sort(np.unique(x))[2:-2]:          # at least 2 laps each side of the bend
        A = np.column_stack([np.ones_like(x), x, np.maximum(0, x - k)])
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        sse = np.sum((A @ coef - y) ** 2)
        if best is None or sse < best[0]:
            best = (sse, k, coef)
    if best is None:                                 # too few laps for a bend
        return fit_linear(x, y)
    _, k, c = best
    return (lambda t: c[0] + c[1] * t + c[2] * np.maximum(0, t - k)), 4


MODELS = {"No wear": fit_none, "Linear": fit_linear, "Quadratic": fit_quadratic, "Cliff": fit_cliff}
NAMES = list(MODELS)

# ---------------- Test every stint ----------------
rows = []
for (drv, stint), g in clean.groupby(["Driver", "Stint"]):
    g = g.sort_values("LapNumber")
    if len(g) < MIN_LAPS:
        continue
    x = g["TyreLife"].to_numpy(float)
    y = g["FuelCorrected"].to_numpy(float)
    n_train = int(len(g) * TRAIN_FRAC)
    row = {"Driver": drv, "Stint": int(stint), "Compound": g["Compound"].iloc[0], "Laps": len(g)}
    for name, fit in MODELS.items():
        pred, _ = fit(x[:n_train], y[:n_train])             # hold-out forecast
        row[f"RMS {name}"] = np.sqrt(np.mean((pred(x[n_train:]) - y[n_train:]) ** 2))
        full, p = fit(x, y)                                 # whole-stint fit
        sse = np.sum((full(x) - y) ** 2)
        row[f"BIC {name}"] = len(y) * np.log(sse / len(y)) + p * np.log(len(y))
    rows.append(row)

res = pd.DataFrame(rows)
rms = res[[f"RMS {n}" for n in NAMES]].set_axis(NAMES, axis=1)
bic = res[[f"BIC {n}" for n in NAMES[1:]]].set_axis(NAMES[1:], axis=1)

print("\n================ DEGRADATION MODEL COMPARISON ================")
print(f"Stints tested: {len(res)} (min {MIN_LAPS} clean laps)\n")
summary = pd.DataFrame({
    "Mean hold-out RMS (s)": rms.mean(),
    "Best forecast (% stints)": rms.idxmin(axis=1).value_counts(normalize=True).reindex(NAMES).fillna(0) * 100,
    "Best by BIC (% stints)": bic.idxmin(axis=1).value_counts(normalize=True).reindex(NAMES).fillna(0) * 100,
})
print(summary.round(2).to_string())

print("\nMean hold-out RMS by compound (s):")
print(res.groupby("Compound")[[f"RMS {n}" for n in NAMES[1:]]].mean().round(2).to_string())

print("\nLeclerc's stints:")
print(res[res["Driver"] == "LEC"][["Stint", "Compound", "Laps"] + [f"RMS {n}" for n in NAMES]]
      .round(2).to_string(index=False))

# ---------------- Plot Leclerc's stints with all three wear models ----------------
lec = clean[clean["Driver"] == "LEC"]
stints = sorted(lec["Stint"].unique())
fig, axes = plt.subplots(1, len(stints), figsize=(5 * len(stints), 4.2))
axes = np.atleast_1d(axes)
for ax, st in zip(axes, stints):
    g = lec[lec["Stint"] == st]
    x = g["TyreLife"].to_numpy(float)
    y = g["FuelCorrected"].to_numpy(float)
    ax.scatter(x, y, color="k", s=18, zorder=3, label="Fuel-corrected laps")
    if len(g) >= 6:
        xs = np.linspace(x.min(), x.max(), 100)
        for name in ["Linear", "Quadratic", "Cliff"]:
            f, _ = MODELS[name](x, y)
            ax.plot(xs, f(xs), lw=2, label=name)
    ax.set_title(f"Leclerc stint {int(st)} ({g['Compound'].iloc[0].title()})")
    ax.set_xlabel("Tyre age (laps)")
axes[0].set_ylabel("Fuel-corrected lap time (s)")
axes[0].legend(fontsize=8)
plt.tight_layout()
plt.savefig("figures/degradation_models.png", dpi=150)
print("\nSaved figures/degradation_models.png")
