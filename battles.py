import fastf1
import numpy as np
import pandas as pd

fastf1.Cache.enable_cache("cache")   # use the same cache folder as your other scripts

YEARS = [2021, 2022]   # only cached races load – F1's API now refuses new downloads
BATTLE_GAP = 1.0       # s – chaser within this gap at start of lap = a battle
CLEAR_AIR_GAP = 2.0    # s – laps with more gap than this count as clear air
MIN_FIT_LAPS = 5       # min laps needed to fit a stint's pace


def load_laps(year):
    s = fastf1.get_session(year, "Hungary", "R")
    s.load(telemetry=False, weather=False, messages=False)
    try:
        laps = s.laps.copy()
    except fastf1.exceptions.DataNotLoadedError:
        print(f"\n*** Skipping {year}: timing data could not be downloaded ***\n")
        return None
    laps["Year"] = year
    laps["LapTimeS"] = laps["LapTime"].dt.total_seconds()
    laps["EndS"] = laps["Time"].dt.total_seconds()          # session time crossing the line
    laps["Pit"] = laps["PitInTime"].notna() | laps["PitOutTime"].notna()
    laps["Green"] = laps["TrackStatus"].astype(str) == "1"  # green flag for the whole lap
    return laps[["Year", "Driver", "LapNumber", "Stint", "LapTimeS", "EndS", "Pit", "Green"]]


def add_gap_ahead(laps):
    # Start of lap N = end of lap N-1
    prev = laps[["Year", "Driver", "LapNumber", "EndS"]].copy()
    prev["LapNumber"] += 1
    prev = prev.rename(columns={"EndS": "StartS"})
    laps = laps.merge(prev, on=["Year", "Driver", "LapNumber"], how="left")
    laps = laps.dropna(subset=["StartS"])                    # drops lap 1
    laps = laps.sort_values(["Year", "LapNumber", "StartS"]).reset_index(drop=True)
    g = laps.groupby(["Year", "LapNumber"])
    laps["AheadDriver"] = g["Driver"].shift(1)
    laps["GapStart"] = laps["StartS"] - g["StartS"].shift(1)
    return laps


def fit_stints(df):
    rows = []
    for (yr, drv, st), grp in df.groupby(["Year", "Driver", "Stint"]):
        if len(grp) < MIN_FIT_LAPS:
            continue
        # Linear in lap number captures fuel burn + tyre wear within a stint
        slope, intercept = np.polyfit(grp["LapNumber"], grp["LapTimeS"], 1)
        rows.append((yr, drv, st, slope, intercept))
    return pd.DataFrame(rows, columns=["Year", "Driver", "Stint", "Slope", "Intercept"])


def add_predicted_pace(laps):
    clean = laps[laps["Green"] & ~laps["Pit"] & laps["LapTimeS"].notna()].copy()
    best = clean.groupby(["Year", "Driver"])["LapTimeS"].transform("min")
    clean = clean[clean["LapTimeS"] < 1.07 * best]           # same 7% rule as clean_laps.py
    clear = clean[(clean["GapStart"] > CLEAR_AIR_GAP) | clean["AheadDriver"].isna()]

    fits_clear = fit_stints(clear)
    fits_clear["PaceSource"] = "clear air"
    fits_all = fit_stints(clean)                             # fallback for drivers stuck in traffic
    fits_all["PaceSource"] = "all laps"
    fits = (pd.concat([fits_clear, fits_all])
              .drop_duplicates(["Year", "Driver", "Stint"], keep="first"))

    laps = laps.merge(fits, on=["Year", "Driver", "Stint"], how="left")
    laps["PredS"] = laps["Intercept"] + laps["Slope"] * laps["LapNumber"]
    return laps


def build_battles(laps):
    ahead = laps[["Year", "LapNumber", "Driver", "LapTimeS", "EndS", "Pit", "Green"]].rename(
        columns={"Driver": "AheadDriver", "LapTimeS": "AheadLapS", "EndS": "AheadEndS",
                 "Pit": "AheadPit", "Green": "AheadGreen"})
    b = laps.merge(ahead, on=["Year", "LapNumber", "AheadDriver"], how="inner")
    b = b[
        (b["GapStart"] > 0) & (b["GapStart"] <= BATTLE_GAP)
        & b["Green"] & b["AheadGreen"] & ~b["Pit"] & ~b["AheadPit"]
        & b["PredS"].notna() & b["AheadLapS"].notna()
    ].copy()
    b["Delta"] = b["AheadLapS"] - b["PredS"]                 # +ve = chaser should be faster
    b["Passed"] = (b["EndS"] < b["AheadEndS"]).astype(int)   # chaser crossed the line first
    return b


if __name__ == "__main__":
    frames = [load_laps(y) for y in YEARS]
    frames = [f for f in frames if f is not None]
    if not frames:
        raise SystemExit("No races loaded – check the cache folder name.")
    laps = pd.concat(frames, ignore_index=True)

    laps = add_gap_ahead(laps)
    laps = add_predicted_pace(laps)
    battles = build_battles(laps)
    battles.to_csv("battles.csv", index=False)

    print("\n================ SUMMARY ================")
    print("Races loaded:", sorted(laps["Year"].unique()))
    print("\nBattles and passes per year:")
    print(battles.groupby("Year")["Passed"].agg(battles="count", passes="sum"))
    print("\nPace prediction source:")
    print(battles["PaceSource"].value_counts())
    print("\nDelta (s/lap) when NO pass:")
    print(battles.loc[battles["Passed"] == 0, "Delta"].describe().round(2))
    print("\nDelta (s/lap) when PASS:")
    print(battles.loc[battles["Passed"] == 1, "Delta"].describe().round(2))
