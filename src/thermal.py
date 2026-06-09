"""Thermal layer: maps IT power to cooling power and PUE.

COP models:
  - "constant"               : flat COP, time-invariant.
  - "chiller_with_economizer": three regimes driven by outdoor T_amb.
      T_amb >= t_full_chiller_c  -> mechanical chiller (linear curve in T_amb)
      T_amb <= t_full_econ_c     -> air-side economizer (free cooling)
      in between                  -> linear blend
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ThermalParams:
    cop_model: str = "constant"
    cop: float = 4.0
    cop_ref: float = 4.0
    cop_temp_slope: float = 0.10
    cop_floor: float = 2.0
    t_ref_c: float = 20.0
    t_full_chiller_c: float = 18.0
    t_full_econ_c: float = 10.0
    cop_econ: float = 20.0
    outdoor_temp: np.ndarray = field(default_factory=lambda: np.zeros(0))

    @classmethod
    def from_config(
        cls,
        config: dict,
        outdoor_temp: np.ndarray | None = None,
    ) -> "ThermalParams":
        t = config.get("thermal", {})
        horizon = int(config["horizon_hours"])
        params = cls(
            cop_model=t.get("cop_model", "constant"),
            cop=float(t.get("cop", 4.0)),
            cop_ref=float(t.get("cop_ref", 4.0)),
            cop_temp_slope=float(t.get("cop_temp_slope", 0.10)),
            cop_floor=float(t.get("cop_floor", 2.0)),
            t_ref_c=float(t.get("t_ref_c", 20.0)),
            t_full_chiller_c=float(t.get("t_full_chiller_c", 18.0)),
            t_full_econ_c=float(t.get("t_full_econ_c", 10.0)),
            cop_econ=float(t.get("cop_econ", 20.0)),
        )
        if params.cop_model == "constant":
            return params

        if outdoor_temp is not None:
            arr = np.asarray(outdoor_temp, dtype=float)
            if arr.shape != (horizon,):
                raise ValueError(
                    f"outdoor_temp shape {arr.shape} != ({horizon},)."
                )
            params.outdoor_temp = arr
            return params

        params.outdoor_temp = _build_outdoor_temp(t.get("outdoor_temp", {}), horizon)
        return params


def _build_outdoor_temp(spec: dict, horizon: int) -> np.ndarray:
    mode = spec.get("mode", "synthetic")
    if mode == "synthetic":
        return synth_outdoor_temp(
            horizon=horizon,
            t_mean_c=float(spec.get("t_mean_c", 16.0)),
            diurnal_amp_c=float(spec.get("diurnal_amp_c", 7.0)),
            peak_hour=int(spec.get("peak_hour", 15)),
            seasonal_drift_amp_c=float(spec.get("seasonal_drift_amp_c", 1.5)),
            seasonal_period_hours=int(spec.get("seasonal_period_hours", 168)),
        )
    if mode == "noaa":
        raise ValueError(
            "outdoor_temp.mode='noaa' requires the caller to load the trace "
            "via data_loader.ensure_outdoor_temp_data() and pass it in."
        )
    raise ValueError(f"Unknown outdoor_temp.mode: {mode}")


def synth_outdoor_temp(
    horizon: int,
    t_mean_c: float = 16.0,
    diurnal_amp_c: float = 7.0,
    peak_hour: int = 15,
    seasonal_drift_amp_c: float = 1.5,
    seasonal_period_hours: int = 168,
) -> np.ndarray:
    """Synthetic outdoor temperature (°C) over `horizon` hours."""
    t = np.arange(horizon)
    diurnal = diurnal_amp_c * np.cos(2.0 * np.pi * (t - peak_hour) / 24.0)
    drift = seasonal_drift_amp_c * np.sin(2.0 * np.pi * t / max(seasonal_period_hours, 1))
    return t_mean_c + diurnal + drift


def cop_from_temp(t_amb: np.ndarray, p: ThermalParams) -> np.ndarray:
    cop_chiller_at = lambda T: np.maximum(p.cop_floor, p.cop_ref - p.cop_temp_slope * (T - p.t_ref_c))

    cop_high = cop_chiller_at(t_amb)
    cop_low = np.full_like(t_amb, p.cop_econ)

    if p.t_full_chiller_c <= p.t_full_econ_c:
        raise ValueError(
            f"t_full_chiller_c ({p.t_full_chiller_c}) must be > t_full_econ_c ({p.t_full_econ_c})"
        )
    span = p.t_full_chiller_c - p.t_full_econ_c
    frac = np.clip((t_amb - p.t_full_econ_c) / span, 0.0, 1.0)
    cop_mid_anchor_high = cop_chiller_at(np.array(p.t_full_chiller_c))
    cop_blend = p.cop_econ + frac * (cop_mid_anchor_high - p.cop_econ)

    cop = np.where(t_amb >= p.t_full_chiller_c, cop_high,
          np.where(t_amb <= p.t_full_econ_c, cop_low, cop_blend))
    return cop


def cop_series(params: ThermalParams, horizon_hours: int) -> np.ndarray:
    if params.cop_model == "constant":
        return np.full(horizon_hours, params.cop, dtype=float)

    if params.cop_model == "chiller_with_economizer":
        if params.outdoor_temp.shape != (horizon_hours,):
            raise ValueError(
                f"outdoor_temp shape {params.outdoor_temp.shape} != ({horizon_hours},)."
            )
        return cop_from_temp(params.outdoor_temp, params)

    raise ValueError(f"Unknown cop_model: {params.cop_model}")


def cooling_power(p_it: np.ndarray, cop: np.ndarray) -> np.ndarray:
    if p_it.shape != cop.shape:
        raise ValueError(f"shape mismatch: P_IT {p_it.shape} vs COP {cop.shape}")
    return p_it / cop


def pue_series(p_it: np.ndarray, p_cooling: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    return (p_it + p_cooling) / np.maximum(p_it, eps)
