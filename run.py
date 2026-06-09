"""run baseline + optimized scenarios, write KPIs."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.data_loader import (
    ensure_lmp_data,
    ensure_outdoor_temp_data,
    load_config,
    season_24h,
    tile_to_horizon,
)
from src.workload import generate_demand_profile, write_demand_csv
from src.baseline import run_baseline
from src.optimizer import solve
from src.thermal import ThermalParams, synth_outdoor_temp


def _build_outdoor_temp_trace(
    config: dict, inputs_dir: Path, horizon: int, season: str,
) -> np.ndarray:
    spec = config.get("thermal", {}).get("outdoor_temp", {})
    mode = spec.get("mode", "synthetic")

    if mode == "noaa":
        noaa = spec.get("noaa", {})
        try:
            temp_df = ensure_outdoor_temp_data(
                inputs_dir,
                lat=float(noaa["lat"]),
                lon=float(noaa["lon"]),
                timezone=noaa.get("timezone", "America/Los_Angeles"),
            )
            temp_24 = season_24h(temp_df, season)
            if temp_24.shape != (24,):
                raise ValueError(f"T_amb shape {temp_24.shape} != (24,)")
            print(f"  T_amb source: Open-Meteo, season={season}, location=({noaa['lat']}, {noaa['lon']})")
            return tile_to_horizon(temp_24, horizon)
        except Exception as exc:
            print(f"  WARNING: T_amb load failed ({exc!r}); falling back to synthetic.")

    print("  T_amb source: synthetic diurnal curve")
    return synth_outdoor_temp(
        horizon=horizon,
        t_mean_c=float(spec.get("t_mean_c", 16.0)),
        diurnal_amp_c=float(spec.get("diurnal_amp_c", 7.0)),
        peak_hour=int(spec.get("peak_hour", 15)),
        seasonal_drift_amp_c=float(spec.get("seasonal_drift_amp_c", 1.5)),
        seasonal_period_hours=int(spec.get("seasonal_period_hours", 168)),
    )


def main() -> None:
    inputs_dir = ROOT / "inputs"
    outputs_dir = ROOT / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / "plots").mkdir(parents=True, exist_ok=True)

    config = load_config(inputs_dir / "config.yaml")
    horizon = int(config["horizon_hours"])
    season = config["supply"]["pricing_season"]

    lmp_df = ensure_lmp_data(inputs_dir)
    price_24 = season_24h(lmp_df, season)
    price = tile_to_horizon(price_24, horizon)

    demand_df = generate_demand_profile(config)
    write_demand_csv(demand_df, inputs_dir / "demand_profile.csv")

    # Build T_amb once and share it across baseline and optimizer.
    t_amb = _build_outdoor_temp_trace(config, inputs_dir, horizon, season)
    thermal_params = ThermalParams.from_config(config, outdoor_temp=t_amb)

    print("=== BASELINE (no deferral, no battery) ===")
    base = run_baseline(demand_df, config, price, thermal=thermal_params)
    print(f"  total_cost      = ${base.total_cost_usd:>10,.2f}")
    print(f"  peak_grid       = {base.peak_grid_mw:>10.2f} MW")
    print(f"  total_grid_mwh  = {base.total_grid_mwh:>10.2f} MWh")
    print(f"  avg_pue         = {base.avg_pue:>10.3f}")
    if base.grid_cap_violation_hours > 0:
        print(
            f"  WARNING: baseline exceeds grid_cap in "
            f"{base.grid_cap_violation_hours}/{horizon} hours"
        )

    print("\n=== OPTIMIZED (joint deferral + battery) ===")
    opt = solve(demand_df, config, price_24, thermal=thermal_params)
    print(f"  solver_status   = {opt.solver_status}")
    print(f"  total_cost      = ${opt.total_cost_usd:>10,.2f}")
    print(f"  peak_grid       = {opt.peak_grid_mw:>10.2f} MW")
    print(f"  total_grid_mwh  = {opt.total_grid_mwh:>10.2f} MWh")
    print(f"  avg_pue         = {opt.avg_pue:>10.3f}")

    cost_sav = base.total_cost_usd - opt.total_cost_usd
    cost_sav_pct = 100.0 * cost_sav / base.total_cost_usd if base.total_cost_usd else 0.0
    peak_sav_pct = 100.0 * (base.peak_grid_mw - opt.peak_grid_mw) / base.peak_grid_mw
    energy_sav_pct = (
        100.0 * (base.total_grid_mwh - opt.total_grid_mwh) / base.total_grid_mwh
        if base.total_grid_mwh else 0.0
    )

    print("\n=== SAVINGS vs BASELINE ===")
    print(f"  cost saved      = ${cost_sav:>10,.2f}  ({cost_sav_pct:5.2f}%)")
    print(f"  peak shaved     = {base.peak_grid_mw - opt.peak_grid_mw:>10.2f} MW  ({peak_sav_pct:5.2f}%)")
    print(f"  energy reduced  = {base.total_grid_mwh - opt.total_grid_mwh:>10.2f} MWh ({energy_sav_pct:5.2f}%)")
    pue_delta = base.avg_pue - opt.avg_pue
    print(f"  PUE improvement = {pue_delta:>10.4f}  ({base.avg_pue:.4f} -> {opt.avg_pue:.4f})")

    t_amb_for_trace = (
        thermal_params.outdoor_temp
        if thermal_params.outdoor_temp.size == horizon
        else np.full(horizon, np.nan)
    )

    trace = pd.DataFrame({
        "hour":        np.arange(horizon),
        "price":       price,
        "t_amb_c":     t_amb_for_trace,
        "p_it_base":   base.p_it,
        "p_it_opt":    opt.p_it,
        "p_cool_base": base.p_cooling,
        "p_cool_opt":  opt.p_cooling,
        "p_grid_base": base.p_grid,
        "p_grid_opt":  opt.p_grid,
        "p_charge":    opt.p_charge,
        "p_discharge": opt.p_discharge,
        "cop":         opt.cop,
    })
    trace.to_csv(outputs_dir / "trace.csv", index=False)

    soc_df = pd.DataFrame({
        "hour": np.arange(horizon + 1),
        "soc_mwh": opt.soc,
    })
    soc_df.to_csv(outputs_dir / "soc_trace.csv", index=False)

    kpi_df = pd.DataFrame([
        {
            "scenario": "baseline",
            "total_cost_usd": base.total_cost_usd,
            "peak_grid_mw": base.peak_grid_mw,
            "total_grid_mwh": base.total_grid_mwh,
            "avg_pue": base.avg_pue,
        },
        {
            "scenario": "optimized",
            "total_cost_usd": opt.total_cost_usd,
            "peak_grid_mw": opt.peak_grid_mw,
            "total_grid_mwh": opt.total_grid_mwh,
            "avg_pue": opt.avg_pue,
        },
    ])
    kpi_df.to_csv(outputs_dir / "kpi_summary.csv", index=False)

    print(f"\nWrote: {outputs_dir/'trace.csv'}")
    print(f"Wrote: {outputs_dir/'soc_trace.csv'}")
    print(f"Wrote: {outputs_dir/'kpi_summary.csv'}")


if __name__ == "__main__":
    main()
