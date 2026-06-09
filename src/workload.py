"""Synthetic IT workload generator (diurnal x day-of-week, mean-normalized)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _diurnal_24h(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    hours = np.arange(24)
    shape = 1.0 + 0.30 * np.sin(2 * np.pi * (hours - 9) / 24)
    noise = rng.normal(0.0, 0.03, size=24)
    return np.clip(shape + noise, 0.1, None)


def _multi_day_profile(seed: int, horizon_hours: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = _diurnal_24h(seed)

    n_days = int(np.ceil(horizon_hours / 24))
    if n_days >= 7:
        dow = np.array([1.02, 1.03, 1.03, 1.02, 1.00, 0.94, 0.93])
        dow_noise = rng.normal(0.0, 0.02, size=7)
        factors = dow + dow_noise
        days = [base * factors[d % 7] for d in range(n_days)]
    else:
        days = [base for _ in range(n_days)]

    profile = np.concatenate(days)[:horizon_hours]
    return profile / profile.mean()


def generate_demand_profile(config: dict) -> pd.DataFrame:
    """Return DataFrame indexed by hour with one column per task name (MW)."""
    seed = int(config.get("seed", 42))
    horizon = int(config.get("horizon_hours", 168))
    total_capacity = float(config["total_capacity_mw"])

    data = {}
    for task in config["tasks"]:
        share = float(task["share_of_demand"])
        per_task_mean = share * total_capacity
        task_seed = seed + hash(task["name"]) % 1000
        task_shape = _multi_day_profile(task_seed, horizon)
        data[task["name"]] = task_shape * per_task_mean

    df = pd.DataFrame(data)
    df.index.name = "hour"
    return df


def write_demand_csv(demand_df: pd.DataFrame, out_path: str | Path) -> None:
    demand_df.to_csv(out_path)


def baseline_power_matrix(
    demand_df: pd.DataFrame,
    config: dict,
) -> dict[str, np.ndarray]:
    return {
        task["name"]: demand_df[task["name"]].to_numpy(dtype=float)
        for task in config["tasks"]
    }
