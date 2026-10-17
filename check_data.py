import fastf1

fastf1.Cache.enable_cache("cache")              # save downloads in the cache folder

session = fastf1.get_session(2022, "Hungary", "R")   # R = race
session.load()                                  # download the data

laps = session.laps                             # a pandas table, one row per lap per driver
lec = laps.pick_drivers("LEC")                  # just Leclerc's laps

print(lec[["LapNumber", "LapTime", "Compound", "TyreLife", "Stint"]].to_string())
