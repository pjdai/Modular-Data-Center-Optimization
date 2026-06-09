"""No-optimization baseline: tasks run at release hour, battery does nothing."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.thermal import ThermalParams, cop_series


@dataclass
class BaselineResult:
    p_it: np.ndarray
    p_cooling: np.ndarray
    p_grid: np.ndarray
    grid_cap_violation_hours: int
    total_cost_usd: float
    peak_grid_mw: float
    total_grid_mwh: float
    avg_pue: float
    cop: np.ndarray
    price: np.ndarray


def run_baseline(
    demand_df: pd.DataFrame,
    config: dict,
    price: np.ndarray,
    thermal: ThermalParams | None = None,
) -> BaselineResult:
    horizon = int(config["horizon_hours"])
    if len(price) != horizon:
        raise ValueError(f"price length {len(price)} != horizon {horizon}")

    p_it = demand_df.sum(axis=1).to_numpy(dtype=float)
    if len(p_it) != horizon:
        raise ValueError(f"demand length {len(p_it)} != horizon {horizon}")

    if thermal is None:
        thermal = ThermalParams.from_config(config)
    cop = cop_series(thermal, horizon)
    p_cooling = p_it / cop

    p_baseload = float(config["supply"]["baseload_mw"])
    grid_cap = float(config["supply"]["grid_cap_mw"])

    p_grid_raw = p_it + p_cooling - p_baseload
    p_grid = np.clip(p_grid_raw, 0.0, None)

    violation_hours = int(np.sum(p_grid > grid_cap + 1e-6))

    total_cost = float(np.sum(price * p_grid))
    peak_grid = float(np.max(p_grid))
    total_grid_energy = float(np.sum(p_grid))
    avg_pue = float((p_it + p_cooling).sum() / np.maximum(p_it.sum(), 1e-9))

    return BaselineResult(
        p_it=p_it,
        p_cooling=p_cooling,
        p_grid=p_grid,
        grid_cap_violation_hours=violation_hours,
        total_cost_usd=total_cost,
        peak_grid_mw=peak_grid,
        total_grid_mwh=total_grid_energy,
        avg_pue=avg_pue,
        cop=cop,
        price=price,
    )
