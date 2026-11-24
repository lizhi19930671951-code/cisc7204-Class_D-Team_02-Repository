"""Audit the supplied NYC monthly Citi Bike release and build its date-level weather join."""
from pathlib import Path
import argparse, calendar, hashlib, json, re, zipfile
from tempfile import TemporaryFile
from shutil import copyfileobj
from collections import Counter
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
STATION = "USW00094728"
DATES = pd.date_range("2023-01-01", "2023-12-31")
TRIP_FIELDS = ["ride_id", "started_at", "ended_at", "start_lat", "start_lng", "member_casual"]

def weather_table(path, station=STATION):
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    weather = raw.loc[raw.STATION.eq(station)].copy()
    weather["date"] = pd.to_datetime(weather.DATE, format="%Y-%m-%d", errors="raise")
    weather = weather.loc[weather.date.isin(DATES)].sort_values("date")
    if weather.date.duplicated().any():
        raise ValueError(f"Duplicate date at {station}")
    d = weather[["date", "STATION"]].rename(columns={"STATION": "station"})
    for col in ("TMAX", "TMIN", "TAVG", "PRCP", "AWND", "SNOW"):
        flags = weather[col + "_ATTRIBUTES"].str.split(",", expand=True).reindex(columns=range(4)).fillna("")
        values = pd.to_numeric(weather[col].replace(["", "9999", "-9999"], np.nan), errors="coerce")
        d[col.lower() + "_raw"] = weather[col]
        d[col.lower() + "_attributes"] = weather[col + "_ATTRIBUTES"]
        d[col.lower()] = values.where(flags[1].eq(""))
        if col == "PRCP":
            d["precip_trace"] = flags[0].eq("T") & d.prcp.notna()
            d["precip_obs_time"] = flags[3]
    d["temp_mid_f"] = (d.tmax + d.tmin) / 2
    d["temp_mid_c"] = (d.temp_mid_f - 32) * 5 / 9
    d["precip_group"] = np.select(
        [d.prcp.isna(), d.prcp.gt(0), d.precip_trace],
        ["Missing", "Measurable", "Trace"], default="Recorded zero")
    if (d.tmax < d.tmin).any() or d.prcp.lt(0).any():
        raise ValueError("Unexpected temperature or precipitation values")
    return d, {"input_rows": len(raw), "stations": raw.STATION.nunique()}

def trip_members(data):
    unpacked = data / "2023-citibike-tripdata"
    if unpacked.is_dir():
        for path in sorted(unpacked.rglob("*.csv")):
            if re.fullmatch(r"2023\d{2}-citibike-tripdata_\d+\.csv", path.name):
                yield path.name, path
        return
    annual = data / "2023-citibike-tripdata.zip"
    if annual.is_file():
        with zipfile.ZipFile(annual) as archive:
            months = sorted(name for name in archive.namelist()
                if re.fullmatch(r"(?:2023-citibike-tripdata/)?2023\d{2}-citibike-tripdata\.zip",name))
            if len(months) != 12:
                raise ValueError("Expected 12 monthly archives in the annual ZIP")
            for name in months:
                # A temporary seekable file avoids re-inflating the outer ZIP on member seeks.
                with archive.open(name) as member, TemporaryFile() as handle:
                    copyfileobj(member,handle,8*1024*1024)
                    handle.seek(0)
                    yield from month_members(handle)
        return
    for path in sorted((data / "2023-citibike-tripdata_zips").glob("2023??-citibike-tripdata.zip")):
        yield from month_members(path)

def month_members(path):
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            filename = Path(name).name
            if re.fullmatch(r"2023\d{2}-citibike-tripdata_\d+\.csv", filename):
                with archive.open(name) as member:
                    yield filename, member

def build_daily(data, output):
    output.mkdir(parents=True, exist_ok=True)
    parts, inventory = [], []
    coord_ranges = [90., -90., 180., -180.]
    for name, source in trip_members(data):
        expected_month = int(name[4:6])
        row = Counter()
        for chunk in pd.read_csv(source, usecols=TRIP_FIELDS, dtype=str, chunksize=400_000):
            start = pd.to_datetime(chunk.started_at, format="mixed", errors="coerce")
            end = pd.to_datetime(chunk.ended_at, format="mixed", errors="coerce")
            good_id = chunk.ride_id.str.fullmatch(r"[0-9a-fA-F]{16}", na=False)
            good_time = start.notna() & end.notna()
            count = len(chunk)
            checks = [~good_id, ~good_time, end.le(start), ~start.between("2023-01-01", "2024-01-01", inclusive="left")]
            reasons = np.select(checks, [1, 2, 3, 4], default=0)
            row["raw"] += count
            for code, reason in enumerate(("valid_before_dedup", "invalid_id", "invalid_timestamp", "nonpositive_naive_duration", "out_of_year")):
                row[reason] += int((reasons == code).sum())
            valid = reasons == 0
            s = start.loc[valid]
            row["start_month_differs_from_archive"] += int(s.dt.month.ne(expected_month).sum())
            row["source_strings_with_offset"] += int(chunk.started_at.str.contains(r"(?:[+-]\d\d:?\d\d|Z)$", na=False).sum())
            lat = pd.to_numeric(chunk.loc[valid, "start_lat"], errors="coerce")
            lng = pd.to_numeric(chunk.loc[valid, "start_lng"], errors="coerce")
            available = lat.notna() & lng.notna()
            row["missing_coordinates"] += int((~available).sum())
            # Broad screen only. The rectangle includes some areas outside NYC.
            envelope = lat.between(40.477, 40.918) & lng.between(-74.260, -73.700)
            row["outside_broad_nyc_rectangle"] += int((available & ~envelope).sum())
            if available.any():
                coord_ranges[0] = min(coord_ranges[0], float(lat[available].min()))
                coord_ranges[1] = max(coord_ranges[1], float(lat[available].max()))
                coord_ranges[2] = min(coord_ranges[2], float(lng[available].min()))
                coord_ranges[3] = max(coord_ranges[3], float(lng[available].max()))
            arr = np.empty(int(valid.sum()), dtype=[("id", "u8"), ("day", "i2"), ("member", "i1"), ("in_rectangle", "i1")])
            arr["id"] = np.fromiter((int(x, 16) for x in chunk.loc[valid,"ride_id"]), dtype=np.uint64, count=len(arr))
            arr["day"] = (s.dt.normalize() - DATES[0]).dt.days.to_numpy()
            arr["member"] = chunk.loc[valid,"member_casual"].map({"casual": 0, "member": 1}).fillna(-1).to_numpy()
            arr["in_rectangle"] = envelope.to_numpy(np.int8)
            parts.append(arr)
        inventory.append({"file": name, **dict(row)})
        print(f"{name} {row['raw']:,} records", flush=True)
    inv = pd.DataFrame(inventory)
    if len(inv) != 40 or len(set(inv.file)) != 40 or set(inv.file.str[4:6]) != {f"{m:02d}" for m in range(1,13)}:
        raise ValueError("Expected the supplied 40 unique CSV shards across 12 months")
    inv.to_csv(output / "trip_inventory.csv",index=False)
    combined = np.concatenate(parts)
    parts.clear()
    order = np.argsort(combined["id"], kind="stable")
    same = combined["id"][order[1:]] == combined["id"][order[:-1]]
    cross_date = int(np.count_nonzero(same & (combined["day"][order[1:]] != combined["day"][order[:-1]])))
    first = order[np.r_[True, ~same]]
    duplicate_n = len(combined) - len(first)
    d = pd.DataFrame({"date": DATES, "ride_count": np.bincount(combined["day"][first], minlength=365)})
    for label, member_mask in (("casual_count", combined["member"][first] == 0), ("member_count", combined["member"][first] == 1),
                                ("other_rider_count", combined["member"][first] == -1), ("rectangle_count", combined["in_rectangle"][first] == 1)):
        d[label] = np.bincount(combined["day"][first[member_mask]], minlength=365)
    del combined, order, same, first
    d["month"] = d.date.dt.month
    d["weekday"] = d.date.dt.dayofweek
    d["is_weekend"] = d.weekday.ge(5)
    weather, weather_meta = weather_table(data/"nyc_weather_2023.csv")
    joined = d.merge(weather, on="date", how="outer", validate="one_to_one", indicator=True).sort_values("date")
    if len(joined) != 365 or not joined._merge.eq("both").all():
        raise ValueError("Incomplete date join")
    joined = joined.drop(columns="_merge")
    joined.to_csv(output/"daily_2023.csv", index=False, float_format="%.10g")
    totals = {k:int(v) for k,v in inv.drop(columns="file").sum().items()}
    excluded = sum(totals[k] for k in ("invalid_id","invalid_timestamp","nonpositive_naive_duration","out_of_year"))
    assert totals["raw"] == excluded + duplicate_n + int(d.ride_count.sum())
    assert (d[["casual_count","member_count","other_rider_count"]].sum(axis=1) == d.ride_count).all()
    audit = {**totals, **{k:int(v) for k,v in weather_meta.items()},
             "shards":len(inv),"retained":int(d.ride_count.sum()),"duplicate_valid":duplicate_n,
             "cross_date_duplicates":cross_date,"joined_days":len(joined),"zero_ride_days":int(d.ride_count.eq(0).sum()),
             "coordinates_minmax":coord_ranges,
             "missing":{col:int(joined[col].isna().sum()) for col in ["tmax","tmin","tavg","prcp","awnd","snow"]},
             "groups":{k:int(v) for k,v in joined.precip_group.value_counts().items()},
             "positive_snow_days":int(joined.snow.gt(0).sum()),
             "prcp_observation_times":{str(k):int(v) for k,v in joined.precip_obs_time.value_counts().items()},
             "scope":"Records from supplied 2023 Citi Bike monthly release (non-JC filenames). Rectangle check is exploratory; no municipal boundary claim.",
             "time_basis":"Date shown in offset-free source timestamps, treated as NYC local civil date. No timezone offset inferred."}
    (output/"audit.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    return joined, audit

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=ROOT/"data"/"raw")
    p.add_argument("--output-dir", type=Path, default=ROOT/"results")
    args = p.parse_args()
    _, audit = build_daily(args.data_dir,args.output_dir)
    print(json.dumps(audit,indent=2))
