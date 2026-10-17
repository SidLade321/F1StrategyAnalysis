import fastf1
import matplotlib.pyplot as plt

fastf1.Cache.enable_cache("cache")
session = fastf1.get_session(2022, "Hungary", "R")
session.load()

lec = session.laps.pick_drivers("LEC")
lec["LapSeconds"] = lec["LapTime"].dt.total_seconds()   # 0:01:24.278 -> 84.278

# Keep only normal racing laps
clean = (lec.pick_wo_box()              # remove in-laps and out-laps
            .pick_track_status("1")     # remove safety car / VSC / yellow-flag laps
            .pick_quicklaps())          # remove anything >7% slower than his best

print(f"Kept {len(clean)} of {len(lec)} laps")

# Plot: all laps in grey, clean laps coloured by tyre
colours = {"SOFT": "red", "MEDIUM": "gold", "HARD": "black"}
plt.figure(figsize=(10, 5))
plt.scatter(lec["LapNumber"], lec["LapSeconds"], color="lightgrey", label="Removed")
for compound, group in clean.groupby("Compound"):
    plt.scatter(group["LapNumber"], group["LapSeconds"],
                color=colours[compound], label=compound)

plt.ylim(80, 90)
plt.xlabel("Lap number")
plt.ylabel("Lap time (s)")
plt.title("Leclerc, Hungary 2022: raw vs cleaned laps")
plt.legend()
plt.grid(alpha=0.3)
plt.savefig("figures/lec_clean_laps.png", dpi=150)
print("Saved figures/lec_clean_laps.png")
