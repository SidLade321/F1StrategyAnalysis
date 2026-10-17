import fastf1
import numpy as np

fastf1.Cache.enable_cache("cache")
session = fastf1.get_session(2022, "Hungary", "R")
session.load()

lec = session.laps.pick_drivers("LEC").copy()
lec["LapSeconds"] = lec["LapTime"].dt.total_seconds()
clean = lec.pick_wo_box().pick_track_status("1").pick_quicklaps().copy()
TOTAL_LAPS = int(lec["LapNumber"].max())
clean = clean[clean["LapNumber"] < TOTAL_LAPS].copy()

ages = np.arange(1, 16)

print(f"{'Fuel s/lap':>10} {'Med1 base':>10} {'Med2 base':>10} "
      f"{'Hard deg':>9} {'Med deg':>8} {'Time lost':>10}")

for fuel in [0.03, 0.04, 0.055, 0.07, 0.08]:
    c = clean.copy()
    c["FuelCorrected"] = c["LapSeconds"] - fuel * (TOTAL_LAPS - c["LapNumber"])
    fits = {}
    for stint, g in c.groupby("Stint"):
        deg, base = np.polyfit(g["TyreLife"], g["FuelCorrected"], 1)
        fits[int(stint)] = (deg, base)

    hard_laps = fits[3][1] + fits[3][0] * ages
    med_laps = fits[2][1] + fits[2][0] * ages
    lost = (hard_laps - med_laps).sum()

    print(f"{fuel:>10.3f} {fits[1][1]:>10.2f} {fits[2][1]:>10.2f} "
          f"{fits[3][0]:>9.3f} {fits[2][0]:>8.3f} {lost:>+10.2f}")
