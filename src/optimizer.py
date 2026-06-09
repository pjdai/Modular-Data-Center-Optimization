"""Joint workload + battery dispatch LP.

Shift-matrix workload deferral LP with battery variables, power balance, and a
thermal layer that links IT power to cooling.
"""
from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np
import pandas as pd

from src.battery import BatteryParams, build_battery_vars
from src.thermal import ThermalParams, cop_series


@dataclass
class OptResult:
    p_it: np.ndarray
    p_cooling: np.ndarray
    p_grid: np.ndarray
    p_charge: np.ndarray
    p_discharge: np.ndarray
    soc: np.ndarray
    power_by_task: dict[str, np.ndarray]

    price: np.ndarray
    cop: np.ndarray

    total_cost_usd: float
    peak_grid_mw: float
    total_grid_mwh: float
    avg_pue: float
    solver_status: str


def _max_window(config: dict) -> int:
    return max(int(t["flexibility_hours"]) for t in config["tasks"])


def _tile_signal(signal_24: np.ndarray, length: int, start_offset: int = 0) -> np.ndarray:
    hours = (np.arange(length) + start_offset) % 24
    return signal_24[hours]


def solve(
    demand_df: pd.DataFrame,
    config: dict,
    price_24: np.ndarray,
    thermal: ThermalParams | None = None,
) -> OptResult:
    horizon = int(config["horizon_hours"])
    w_max = _max_window(config)
    h_pad = horizon + 2 * w_max

    # Workload shift-matrix layer
    constraints: list = []
    p_it_padded = cp.Constant(np.zeros(h_pad))
    per_task_power_padded: dict[str, cp.Expression] = {}

    total_capacity = float(config["total_capacity_mw"])
    p_it_max = float(config.get("peak_multiplier", 1.30)) * total_capacity

    for task in config["tasks"]:
        name = task["name"]
        w = int(task["flexibility_hours"])
        d_k = demand_df[name].to_numpy(dtype=float)
        X = cp.Variable((horizon, w + 1), nonneg=True, name=f"X_{name}")
        constraints.append(cp.sum(X, axis=1) == 1)

        if w > 0:
            valid_mask = np.zeros((horizon, w + 1))
            for t in range(horizon):
                max_s = min(w, horizon - 1 - t)
                valid_mask[t, : max_s + 1] = 1.0
            invalid_mask = 1.0 - valid_mask
            if invalid_mask.any():
                constraints.append(cp.multiply(invalid_mask, X) == 0)

        task_power = cp.Constant(np.zeros(h_pad))
        for s in range(w + 1):
            contribution = cp.multiply(d_k, X[:, s])
            left_pad = w_max + s
            right_pad = h_pad - left_pad - horizon
            pieces: list = []
            if left_pad > 0:
                pieces.append(np.zeros(left_pad))
            pieces.append(contribution)
            if right_pad > 0:
                pieces.append(np.zeros(right_pad))
            padded = cp.hstack(pieces) if len(pieces) > 1 else pieces[0]
            task_power = task_power + padded
        per_task_power_padded[name] = task_power
        p_it_padded = p_it_padded + task_power

        share = float(task["share_of_demand"])
        mult = float(task.get("max_power_multiplier", 2.0))
        per_task_cap = mult * share * total_capacity
        constraints.append(task_power <= per_task_cap)

    constraints.append(p_it_padded <= p_it_max)

    inner = slice(w_max, w_max + horizon)
    p_it = p_it_padded[inner]

    # Thermal layer
    if thermal is None:
        thermal = ThermalParams.from_config(config)
    cop = cop_series(thermal, horizon)
    p_cooling = cp.multiply(1.0 / cop, p_it)

    # Battery layer
    bat_params = BatteryParams.from_config(config)
    p_charge, p_discharge, soc, bat_constraints = build_battery_vars(bat_params, horizon)
    constraints += bat_constraints

    # Power balance + grid cap
    supply = config["supply"]
    p_baseload = float(supply["baseload_mw"])
    grid_cap = float(supply["grid_cap_mw"])

    p_grid = cp.Variable(horizon, nonneg=True, name="p_grid")

    constraints.append(
        p_baseload + p_grid + p_discharge == p_it + p_cooling + p_charge
    )
    constraints.append(p_grid <= grid_cap)

    # Objective: minimize grid cost + battery degradation
    price = _tile_signal(price_24, horizon, start_offset=0)
    deg_cost = bat_params.degradation_cost_usd_per_mwh
    objective = cp.Minimize(
        cp.sum(cp.multiply(price, p_grid))
        + deg_cost * cp.sum(p_charge)
    )

    prob = cp.Problem(objective, constraints)
    prob.solve(solver=cp.CLARABEL)

    p_it_val = np.asarray(p_it.value).flatten()
    p_cooling_val = p_it_val / cop
    p_grid_val = np.asarray(p_grid.value).flatten()
    p_charge_val = np.asarray(p_charge.value).flatten()
    p_discharge_val = np.asarray(p_discharge.value).flatten()
    soc_val = np.asarray(soc.value).flatten()

    power_by_task = {}
    for name, expr in per_task_power_padded.items():
        v = np.asarray(expr.value).flatten()
        power_by_task[name] = v[w_max:w_max + horizon]

    total_cost = float(np.sum(price * p_grid_val))
    peak_grid = float(np.max(p_grid_val))
    total_grid_energy = float(np.sum(p_grid_val))
    avg_pue = float((p_it_val + p_cooling_val).sum() / np.maximum(p_it_val.sum(), 1e-9))

    return OptResult(
        p_it=p_it_val,
        p_cooling=p_cooling_val,
        p_grid=p_grid_val,
        p_charge=p_charge_val,
        p_discharge=p_discharge_val,
        soc=soc_val,
        power_by_task=power_by_task,
        price=price,
        cop=cop,
        total_cost_usd=total_cost,
        peak_grid_mw=peak_grid,
        total_grid_mwh=total_grid_energy,
        avg_pue=avg_pue,
        solver_status=prob.status,
    )
