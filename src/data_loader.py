"""TOU electricity price + outdoor temperature loaders.

CAISO LMP via gridstatus (with fallback profile). Outdoor temperature via
Open-Meteo's historical archive API (free, no key).
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import date, timedelta

import numpy as np
import pandas as pd
import yaml


CAISO_NODE = "TH_NP15_GEN-APND"

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

SEASON_RANGES = {
    "summer":   (date(2024, 7, 1), date(2024, 7, 31)),
    "winter":   (date(2024, 1, 1), date(2024, 1, 31)),
    "shoulder": (date(2024, 4, 1), date(2024, 4, 30)),
}

# Fallback CAISO NP15 LMP profile if gridstatus is unavailable.
FALLBACK_LMP = {
    "summer": [
        42, 38, 35, 33, 33, 36, 44, 55,
        48, 35, 25, 20, 18, 17, 22, 35,
        58, 95, 120, 110, 88, 70, 58, 48,
    ],
    "winter": [
        55, 52, 50, 48, 50, 58, 75, 90,
        82, 70, 62, 58, 55, 57, 62, 78,
        100, 110, 102, 92, 82, 72, 65, 60,
    ],
    "shoulder": [
        38, 35, 32, 30, 30, 33, 42, 52,
        42, 30, 22, 18, 16, 15, 18, 28,
        48, 72, 85, 80, 68, 55, 48, 42,
    ],
}


def load_config(path: str | Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _fetch_caiso_lmp_day(date_str: str) -> list[float] | None:
    try:
        import gridstatus
    except ImportError:
        return None
    try:
        iso = gridstatus.CAISO()
        df = iso.get_lmp(
            date=date_str,
            market="DAY_AHEAD_HOURLY",
            locations=[CAISO_NODE],
        )
        df = df.sort_values("Time").reset_index(drop=True)
        lmp_col = "LMP" if "LMP" in df.columns else df.columns[-1]
        values = df[lmp_col].to_numpy(dtype=float)
        if len(values) < 24:
            return None
        return values[:24].tolist()
    except Exception:
        return None


def _daterange(start: date, end: date) -> list[str]:
    days = (end - start).days + 1
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]


def _fetch_30day_avg(season: str) -> tuple[list[float], str]:
    start, end = SEASON_RANGES[season]
    dates = _daterange(start, end)
    collected: list[list[float]] = []
    for d in dates:
        s = _fetch_caiso_lmp_day(d)
        if s is not None and len(s) >= 24:
            collected.append(s[:24])
    if len(collected) < 7:
        return FALLBACK_LMP[season], f"fallback_cached_only_{len(collected)}_days"
    avg = np.mean(np.array(collected, dtype=float), axis=0)
    print(f"  [{season}] averaged {len(collected)}/{len(dates)} days of CAISO LMP")
    return avg.tolist(), "caiso_api_30day_avg"


def build_lmp_csv(out_path: str | Path) -> pd.DataFrame:
    rows = []
    for season in SEASON_RANGES:
        values, source = _fetch_30day_avg(season)
        for hour, v in enumerate(values, start=1):
            rows.append({
                "season": season,
                "hour": hour,
                "value": float(v),
                "source": source,
            })
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    return df


def ensure_lmp_data(
    inputs_dir: str | Path,
    force_refresh: bool = False,
) -> pd.DataFrame:
    inputs_dir = Path(inputs_dir)
    lmp_path = inputs_dir / "energy_cost.csv"
    if force_refresh or not lmp_path.exists():
        build_lmp_csv(lmp_path)
    return pd.read_csv(lmp_path)


def season_24h(df: pd.DataFrame, season: str) -> np.ndarray:
    sub = df[df["season"] == season].sort_values("hour")
    return sub["value"].to_numpy(dtype=float)


def tile_to_horizon(signal_24: np.ndarray, horizon_hours: int) -> np.ndarray:
    hours = np.arange(horizon_hours) % 24
    return signal_24[hours]


def _fetch_open_meteo_hourly_temp(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    timezone: str,
) -> list[tuple[str, float]] | None:
    params = {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m",
        "timezone": timezone,
    }
    url = OPEN_METEO_ARCHIVE_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    try:
        times = payload["hourly"]["time"]
        temps = payload["hourly"]["temperature_2m"]
    except (KeyError, TypeError):
        return None
    if not times or not temps or len(times) != len(temps):
        return None
    if any(v is None for v in temps):
        return None
    return [(str(t), float(v)) for t, v in zip(times, temps)]


def _fetch_30day_avg_temp(
    season: str,
    lat: float,
    lon: float,
    timezone: str,
) -> tuple[list[float] | None, str]:
    start, end = SEASON_RANGES[season]
    series = _fetch_open_meteo_hourly_temp(
        lat, lon, start.isoformat(), end.isoformat(), timezone
    )
    if series is None:
        return None, "open_meteo_unavailable"
    buckets: list[list[float]] = [[] for _ in range(24)]
    for time_str, temp in series:
        try:
            hour = int(time_str.split("T")[1].split(":")[0])
        except (IndexError, ValueError):
            continue
        if 0 <= hour < 24:
            buckets[hour].append(temp)
    if any(len(b) < 7 for b in buckets):
        return None, "insufficient_coverage"
    avg = [float(np.mean(b)) for b in buckets]
    print(f"  [{season}] averaged {len(series)} hours of Open-Meteo T_amb at ({lat:.3f}, {lon:.3f})")
    return avg, "open_meteo_30day_avg"


def _synthetic_temp_24h(season: str) -> list[float]:
    seasonal = {
        "summer":   (24.0, 9.0),
        "winter":   (8.0,  4.0),
        "shoulder": (16.0, 7.0),
    }
    t_mean, amp = seasonal.get(season, (16.0, 7.0))
    hours = np.arange(24)
    return (t_mean + amp * np.cos(2.0 * np.pi * (hours - 15) / 24.0)).tolist()


def build_temp_csv(
    out_path: str | Path,
    lat: float,
    lon: float,
    timezone: str = "America/Los_Angeles",
) -> pd.DataFrame:
    rows = []
    for season in SEASON_RANGES:
        values, source = _fetch_30day_avg_temp(season, lat, lon, timezone)
        if values is None:
            print(f"  [{season}] WARNING: fetch failed ({source}); using synthetic fallback")
            values = _synthetic_temp_24h(season)
            source = f"synthetic_fallback_{source}"
        for hour, v in enumerate(values, start=1):
            rows.append({
                "season": season,
                "hour": hour,
                "value": float(v),
                "source": source,
            })
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    return df


def ensure_outdoor_temp_data(
    inputs_dir: str | Path,
    lat: float,
    lon: float,
    timezone: str = "America/Los_Angeles",
) -> pd.DataFrame:
    inputs_dir = Path(inputs_dir)
    temp_path = inputs_dir / "outdoor_temp.csv"
    if not temp_path.exists():
        print(f"Building {temp_path} from Open-Meteo at ({lat}, {lon}) ...")
        build_temp_csv(temp_path, lat, lon, timezone)
    return pd.read_csv(temp_path)
