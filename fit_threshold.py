import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression

b = pd.read_csv("battles.csv")
rng = np.random.default_rng(0)


def fit(X, y):
    m = LogisticRegression(C=np.inf, max_iter=1000).fit(X, y)
    return -m.intercept_[0] / m.coef_[0][0], m   # delta where P(pass) = 50%


def threshold_with_ci(df, n_boot=1000):
    X = df[["Delta"]].to_numpy()
    y = df["Passed"].to_numpy()
    thr, model = fit(X, y)
    boot = []
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        boot.append(fit(X[i], y[i])[0])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return thr, lo, hi, model


groups = {"2021": b[b["Year"] == 2021], "2022": b[b["Year"] == 2022], "Both": b}
results = {}

print(f"\n{'Data':<6}{'Battles':>9}{'Passes':>8}{'Threshold':>12}   95% CI")
for name, df in groups.items():
    thr, lo, hi, model = threshold_with_ci(df)
    results[name] = (thr, lo, hi, model)
    print(f"{name:<6}{len(df):>9}{df['Passed'].sum():>8}{thr:>10.2f} s   {lo:.2f} to {hi:.2f} s")

# Plot
xs = np.linspace(b["Delta"].min(), b["Delta"].max(), 300).reshape(-1, 1)
plt.figure(figsize=(9, 5.5))
for year, colour in [(2021, "tab:blue"), (2022, "tab:red")]:
    d = b[b["Year"] == year]
    jitter = rng.uniform(-0.04, 0.04, len(d))
    plt.scatter(d["Delta"], d["Passed"] + jitter, alpha=0.35, s=18, color=colour)
    thr, lo, hi, model = results[str(year)]
    plt.plot(xs, model.predict_proba(xs)[:, 1], lw=2, color=colour,
             label=f"{year}: 50% threshold = {thr:.2f} s ({lo:.2f}–{hi:.2f})")

thr22, lo22, hi22, _ = results["2022"]
plt.axvspan(lo22, hi22, alpha=0.12, color="tab:red")
plt.axvline(thr22, ls="--", color="tab:red")
plt.xlabel("Chaser's predicted pace advantage over car ahead (s/lap)")
plt.ylabel("Pass probability")
plt.title("Overtaking threshold at the Hungaroring: 2021 vs 2022 cars")
plt.legend(loc="lower right")
plt.tight_layout()
plt.savefig("figures/overtake_threshold.png", dpi=150)
print("\nSaved figures/overtake_threshold.png")
