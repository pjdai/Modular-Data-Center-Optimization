"""Sensitivity sweeps: battery capacity and geographic location."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_loader import (
    ensure_lmp_data,
    ensure_outdoor_temp_data,
    load_config,
    season_24h,
    tile_to_horizon,
)
from src.workload import generate_demand_profile
from src.baseline import run_baseline
from src.optimizer import solve
from src.thermal import ThermalParams


def _build_t_amb(
    config: dict, inputs_dir: Path, horizon: int, season: str,
) -> np.ndarray:
    spec = config["thermal"]["outdoor_temp"]
    noaa = spec["noaa"]
    temp_df = ensure_outdoor_temp_data(
        inputs_dir,
        lat=float(noaa["lat"]),
        lon=float(noaa["lon"]),
        timezone=noaa.get("timezone", "America/Los_Angeles"),
    )
    temp_24 = season_24h(temp_df, season)
    return tile_to_horizon(temp_24, horizon)


def sweep_battery(
    base_config: dict,
    price: np.ndarray,
    price_24: np.ndarray,
    demand_df: pd.DataFrame,
    thermal_params: ThermalParams,
    capacities: list[float],
) -> pd.DataFrame:
    rows = []
    for cap in capacities:
        cfg = copy.deepcopy(base_config)
        cfg["battery"]["capacity_mwh"] = float(cap)
        cfg["battery"]["power_max_mw"] = float(cap) * 0.5  # fixed C-rate

        base = run_baseline(demand_df, cfg, price, thermal=thermal_params)
        opt = solve(demand_df, cfg, price_24, thermal=thermal_params)

        cost_sav_pct = (
            100.0 * (base.total_cost_usd - opt.total_cost_usd) / base.total_cost_usd
            if base.total_cost_usd else 0.0
        )
        rows.append({
            "capacity_mwh": float(cap),
            "cost_saving_pct": cost_sav_pct,
            "peak_grid_mw": opt.peak_grid_mw,
            "avg_pue": opt.avg_pue,
            "total_grid_mwh": opt.total_grid_mwh,
        })
        print(
            f"  cap={cap:>4.1f} MWh  "
            f"saving={cost_sav_pct:>5.2f}%  "
            f"peak={opt.peak_grid_mw:>5.2f} MW  "
            f"PUE={opt.avg_pue:.4f}  "
            f"grid={opt.total_grid_mwh:>7.2f} MWh"
        )
    return pd.DataFrame(rows)


def sweep_geo(
    base_config: dict,
    inputs_dir: Path,
    price: np.ndarray,
    price_24: np.ndarray,
    demand_df: pd.DataFrame,
    cities: list[dict],
) -> pd.DataFrame:
    horizon = int(base_config["horizon_hours"])
    season = base_config["supply"]["pricing_season"]
    temp_csv = inputs_dir / "outdoor_temp.csv"
    rows = []

    for city in cities:
        # Clear cache so each city pulls fresh weather data.
        if temp_csv.exists():
            temp_csv.unlink()

        cfg = copy.deepcopy(base_config)
        noaa = cfg["thermal"]["outdoor_temp"]["noaa"]
        noaa["lat"] = city["lat"]
        noaa["lon"] = city["lon"]
        noaa["timezone"] = city["timezone"]

        t_amb = _build_t_amb(cfg, inputs_dir, horizon, season)
        tp = ThermalParams.from_config(cfg, outdoor_temp=t_amb)

        base = run_baseline(demand_df, cfg, price, thermal=tp)
        opt = solve(demand_df, cfg, price_24, thermal=tp)

        cost_sav_pct = (
            100.0 * (base.total_cost_usd - opt.total_cost_usd) / base.total_cost_usd
            if base.total_cost_usd else 0.0
        )
        rows.append({
            "city": city["name"],
            "avg_T_amb_c": float(np.mean(t_amb)),
            "avg_cop": float(np.mean(opt.cop)),
            "cost_saving_pct": cost_sav_pct,
            "avg_pue_baseline": base.avg_pue,
            "avg_pue_optimized": opt.avg_pue,
            "pue_delta": base.avg_pue - opt.avg_pue,
        })
        print(
            f"  {city['name']:<11}  "
            f"T={np.mean(t_amb):>5.2f}C  "
            f"COP={np.mean(opt.cop):>5.2f}  "
            f"saving={cost_sav_pct:>5.2f}%  "
            f"PUE: {base.avg_pue:.4f} -> {opt.avg_pue:.4f}"
        )

    # Restore Sacramento cache so subsequent run.py invocations don't inherit
    # the last sweep city.
    if temp_csv.exists():
        temp_csv.unlink()
    sac_noaa = base_config["thermal"]["outdoor_temp"]["noaa"]
    ensure_outdoor_temp_data(
        inputs_dir,
        lat=float(sac_noaa["lat"]),
        lon=float(sac_noaa["lon"]),
        timezone=sac_noaa.get("timezone", "America/Los_Angeles"),
    )

    return pd.DataFrame(rows)


def main() -> None:
    inputs_dir = ROOT / "inputs"
    outputs_dir = ROOT / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    base_config = load_config(inputs_dir / "config.yaml")
    horizon = int(base_config["horizon_hours"])
    season = base_config["supply"]["pricing_season"]

    lmp_df = ensure_lmp_data(inputs_dir, force_refresh=False)
    price_24 = season_24h(lmp_df, season)
    price = tile_to_horizon(price_24, horizon)

    demand_df = generate_demand_profile(base_config)

    print("=== SWEEP 1: battery capacity (Sacramento, shoulder) ===")
    t_amb_sac = _build_t_amb(base_config, inputs_dir, horizon, season)
    thermal_params_sac = ThermalParams.from_config(
        base_config, outdoor_temp=t_amb_sac
    )
    capacities = [1.0, 2.0, 4.0, 6.0, 8.0, 10.0]
    df_bat = sweep_battery(
        base_config, price, price_24, demand_df, thermal_params_sac, capacities,
    )
    bat_path = outputs_dir / "sweep_battery.csv"
    df_bat.to_csv(bat_path, index=False)
    print(f"\nWrote: {bat_path}")
    print(df_bat.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n=== SWEEP 2: geographic (default battery, shoulder) ===")
    # Placeholder coordinates — fill in real lat/lon per city to reproduce
    # the geographic sweep against live weather data.
    cities = [
        {"name": "Sacramento", "lat": 0.0, "lon": 0.0,
         "timezone": "America/Los_Angeles"},
        {"name": "Phoenix",    "lat": 0.0, "lon": 0.0,
         "timezone": "America/Phoenix"},
        {"name": "Stockholm",  "lat": 0.0, "lon": 0.0,
         "timezone": "Europe/Stockholm"},
    ]
    df_geo = sweep_geo(
        base_config, inputs_dir, price, price_24, demand_df, cities,
    )
    geo_path = outputs_dir / "sweep_geo.csv"
    df_geo.to_csv(geo_path, index=False)
    print(f"\nWrote: {geo_path}")
    print(df_geo.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
