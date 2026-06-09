"""Battery storage: SoC dynamics and cvxpy variables."""
from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np


@dataclass
class BatteryParams:
    capacity_mwh: float
    power_max_mw: float
    eta_charge: float
    eta_discharge: float
    soc_min_frac: float
    soc_max_frac: float
    soc_initial_frac: float
    degradation_cost_usd_per_mwh: float = 15.0

    @classmethod
    def from_config(cls, config: dict) -> "BatteryParams":
        b = config["battery"]
        return cls(
            capacity_mwh=float(b["capacity_mwh"]),
            power_max_mw=float(b["power_max_mw"]),
            eta_charge=float(b["eta_charge"]),
            eta_discharge=float(b["eta_discharge"]),
            soc_min_frac=float(b["soc_min_frac"]),
            soc_max_frac=float(b["soc_max_frac"]),
            soc_initial_frac=float(b["soc_initial_frac"]),
            degradation_cost_usd_per_mwh=float(b.get("degradation_cost_usd_per_mwh", 15.0)),
        )

    @property
    def soc_min(self) -> float:
        return self.soc_min_frac * self.capacity_mwh

    @property
    def soc_max(self) -> float:
        return self.soc_max_frac * self.capacity_mwh

    @property
    def soc_initial(self) -> float:
        return self.soc_initial_frac * self.capacity_mwh


def simulate_battery_passthrough(horizon_hours: int) -> dict[str, np.ndarray]:
    """Baseline: battery does nothing."""
    z = np.zeros(horizon_hours)
    return {
        "p_charge": z.copy(),
        "p_discharge": z.copy(),
        "soc": z.copy(),
    }


def build_battery_vars(
    params: BatteryParams,
    horizon_hours: int,
) -> tuple[cp.Variable, cp.Variable, cp.Variable, list]:
    p_c = cp.Variable(horizon_hours, nonneg=True, name="p_charge")
    p_d = cp.Variable(horizon_hours, nonneg=True, name="p_discharge")
    soc = cp.Variable(horizon_hours + 1, name="soc")

    constraints = []

    constraints.append(p_c <= params.power_max_mw)
    constraints.append(p_d <= params.power_max_mw)

    constraints.append(soc >= params.soc_min)
    constraints.append(soc <= params.soc_max)

    # SoC[t+1] = SoC[t] + eta_c * p_c[t] - p_d[t] / eta_d
    constraints.append(
        soc[1:] == soc[:-1] + params.eta_charge * p_c - p_d / params.eta_discharge
    )

    constraints.append(soc[0] == params.soc_initial)
    constraints.append(soc[-1] == params.soc_initial)

    return p_c, p_d, soc, constraints
