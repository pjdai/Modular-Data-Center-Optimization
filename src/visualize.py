"""Publication plots: dispatch trace, battery sweep, geographic sweep, SoC trajectory."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUTS = ROOT / "outputs"
PLOTS = OUTPUTS / "plots"
INPUTS = ROOT / "inputs"

FS_TITLE = 13
FS_AXIS = 11
FS_TICK = 9
FS_ANNOT = 9

COL_TAMB     = "#a8d8ea"
COL_PRICE    = "#f39c12"
COL_BASE     = "#e74c3c"
COL_OPT      = "#2ecc71"
COL_BAT      = "#3498db"
COL_PHOENIX  = "#e74c3c"
COL_SACTO    = "#f39c12"
COL_STKHLM   = "#2ecc71"


def _ensure_trace() -> None:
    trace = OUTPUTS / "trace.csv"
    soc = OUTPUTS / "soc_trace.csv"
    if trace.exists() and soc.exists():
        return
    print("trace.csv missing — running run.py to generate it...")
    subprocess.run([sys.executable, str(ROOT / "run.py")], check=True)


def _load_config() -> dict:
    with open(INPUTS / "config.yaml", "r") as f:
        return yaml.safe_load(f)


def _style_ticks(ax) -> None:
    ax.tick_params(axis="both", labelsize=FS_TICK)
    ax.grid(True, alpha=0.3)


def fig1_dispatch_48h(out_path: Path) -> None:
    trace = pd.read_csv(OUTPUTS / "trace.csv")
    soc_df = pd.read_csv(OUTPUTS / "soc_trace.csv")
    config = _load_config()

    grid_cap = float(config["supply"]["grid_cap_mw"])
    bat = config["battery"]
    soc_min = bat["capacity_mwh"] * bat["soc_min_frac"]
    soc_max = bat["capacity_mwh"] * bat["soc_max_frac"]

    n = 48
    h = trace["hour"].to_numpy()[:n]
    t_amb = trace["t_amb_c"].to_numpy()[:n]
    price = trace["price"].to_numpy()[:n]
    p_grid_base = trace["p_grid_base"].to_numpy()[:n]
    p_grid_opt = trace["p_grid_opt"].to_numpy()[:n]
    soc = soc_df["soc_mwh"].to_numpy()[:n + 1]
    soc_h = soc_df["hour"].to_numpy()[:n + 1]

    fig, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True)

    ax = axes[0]
    ax.fill_between(h, t_amb, color=COL_TAMB, alpha=0.85, label="T_amb")
    ax.plot(h, t_amb, color="#5fa8c9", linewidth=1.2)
    ax.axhline(10, color="black", linestyle="--", linewidth=1.0, alpha=0.6)
    ax.axhline(18, color="black", linestyle="--", linewidth=1.0, alpha=0.6)
    ax.text(n - 0.5, 10, " full econ", va="center", ha="left", fontsize=FS_ANNOT)
    ax.text(n - 0.5, 18, " full chiller", va="center", ha="left", fontsize=FS_ANNOT)
    ax.set_ylabel("T_amb (°C)", fontsize=FS_AXIS)
    _style_ticks(ax)

    ax = axes[1]
    ax.step(h, price, where="post", color=COL_PRICE, linewidth=1.6)
    ax.fill_between(h, price, step="post", color=COL_PRICE, alpha=0.25)
    ax.set_ylabel("Price ($/MWh)", fontsize=FS_AXIS)
    _style_ticks(ax)

    ax = axes[2]
    ax.plot(h, p_grid_base, color=COL_BASE, linestyle="--", linewidth=1.6,
            label="Baseline")
    ax.plot(h, p_grid_opt, color=COL_OPT, linestyle="-", linewidth=1.8,
            label="Optimized")
    ax.axhline(grid_cap, color="black", linestyle="--", linewidth=1.0, alpha=0.6)
    ax.text(n - 0.5, grid_cap, " grid cap", va="center", ha="left", fontsize=FS_ANNOT)
    ax.set_ylabel("Grid draw (MW)", fontsize=FS_AXIS)
    ax.legend(loc="upper left", fontsize=FS_ANNOT, framealpha=0.9)
    _style_ticks(ax)

    ax = axes[3]
    ax.axhspan(soc_min, soc_max, color=COL_BAT, alpha=0.15)
    ax.plot(soc_h, soc, color=COL_BAT, linewidth=1.8)
    ax.axhline(soc_min, color=COL_BAT, linestyle=":", linewidth=1.0, alpha=0.7)
    ax.axhline(soc_max, color=COL_BAT, linestyle=":", linewidth=1.0, alpha=0.7)
    ax.set_ylabel("Battery SoC (MWh)", fontsize=FS_AXIS)
    ax.set_xlabel("Hour of simulation", fontsize=FS_AXIS)
    _style_ticks(ax)
    ax.set_xlim(0, n - 1)

    fig.suptitle(
        "48-hour Dispatch Trace — Sacramento, April (Shoulder Season)",
        fontsize=FS_TITLE,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig2_battery_sweep(out_path: Path) -> None:
    df = pd.read_csv(OUTPUTS / "sweep_battery.csv").sort_values("capacity_mwh")
    cap = df["capacity_mwh"].to_numpy()
    sav = df["cost_saving_pct"].to_numpy()

    sav_at = dict(zip(cap.tolist(), sav.tolist()))
    gain_low = sav_at[4.0] - sav_at[1.0]
    gain_high = sav_at[10.0] - sav_at[4.0]
    gain_high_per_mwh = gain_high / 6.0

    fig, ax = plt.subplots(figsize=(9, 6))

    y_lo, y_hi = 30.0, max(sav.max() + 0.6, 35.0)
    ax.axvspan(1.0, 4.0, color="#2ecc71", alpha=0.12)
    ax.axvspan(4.0, 10.0, color="#95a5a6", alpha=0.12)
    ax.text(2.5, y_hi - 0.5, "high marginal value",
            ha="center", fontsize=FS_ANNOT, color="#1e8449")
    ax.text(7.0, y_hi - 0.5, "diminishing returns",
            ha="center", fontsize=FS_ANNOT, color="#566573")

    ax.plot(cap, sav, color=COL_BAT, linewidth=2.2, marker="o",
            markersize=8, markerfacecolor="white", markeredgecolor=COL_BAT,
            markeredgewidth=1.8, label="Cost saving %")

    sav_default = sav_at[4.0]
    ax.plot(4.0, sav_default, marker="*", markersize=20,
            color=COL_BASE, markeredgecolor="black", markeredgewidth=0.8,
            zorder=6, label="default (4 MWh)")

    ax.text(
        0.98, 0.04,
        f"1→4 MWh: +{gain_low:.2f} pp\n"
        f"4→10 MWh: +{gain_high:.2f} pp total, +{gain_high_per_mwh:.2f} pp/MWh",
        transform=ax.transAxes, ha="right", va="bottom",
        fontsize=FS_ANNOT,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                  edgecolor="#bdc3c7", alpha=0.9),
    )

    ax.set_xlabel("Battery capacity (MWh)", fontsize=FS_AXIS)
    ax.set_ylabel("Cost saving vs baseline (%)", fontsize=FS_AXIS)
    ax.set_title("Cost Saving vs Battery Capacity (Sacramento)", fontsize=FS_TITLE)
    ax.set_xlim(0.5, 10.5)
    ax.set_ylim(y_lo, y_hi)
    ax.legend(loc="upper left", fontsize=FS_ANNOT, framealpha=0.9)
    _style_ticks(ax)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig3_geo_comparison(out_path: Path) -> None:
    df = pd.read_csv(OUTPUTS / "sweep_geo.csv")
    order = ["Phoenix", "Sacramento", "Stockholm"]
    df = df.set_index("city").loc[order].reset_index()
    colors = {
        "Phoenix": COL_PHOENIX,
        "Sacramento": COL_SACTO,
        "Stockholm": COL_STKHLM,
    }

    fig, axes = plt.subplots(1, 2, figsize=(13, 6))

    ax = axes[0]
    x = np.arange(len(order))
    w = 0.36
    pue_b = df["avg_pue_baseline"].to_numpy()
    pue_o = df["avg_pue_optimized"].to_numpy()

    bars_b = ax.bar(
        x - w / 2, pue_b, w,
        color=[colors[c] for c in order], alpha=0.45,
        hatch="//", edgecolor="black", linewidth=0.8,
        label="Baseline",
    )
    bars_o = ax.bar(
        x + w / 2, pue_o, w,
        color=[colors[c] for c in order], alpha=0.95,
        edgecolor="black", linewidth=0.8,
        label="Optimized",
    )

    for bar, val in zip(list(bars_b) + list(bars_o), list(pue_b) + list(pue_o)):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.005,
            f"{val:.4f}", ha="center", va="bottom", fontsize=FS_ANNOT,
        )

    ax.axhline(1.0, color="black", linestyle="--", linewidth=1.0, alpha=0.6)
    ax.text(len(order) - 0.5, 1.0, " theoretical minimum",
            va="center", ha="left", fontsize=FS_ANNOT)

    ax.set_xticks(x)
    ax.set_xticklabels(order, fontsize=FS_TICK)
    ax.set_ylabel("Average PUE (energy-weighted)", fontsize=FS_AXIS)
    ax.set_ylim(0.97, max(pue_b.max(), pue_o.max()) + 0.05)
    ax.legend(loc="upper left", fontsize=FS_ANNOT, framealpha=0.9)
    _style_ticks(ax)

    ax = axes[1]
    sav = df["cost_saving_pct"].to_numpy()
    y = np.arange(len(order))
    bars = ax.barh(
        y, sav,
        color=[colors[c] for c in order],
        edgecolor="black", linewidth=0.8,
    )
    for bar, v in zip(bars, sav):
        ax.text(
            bar.get_width() + 0.2,
            bar.get_y() + bar.get_height() / 2,
            f"{v:.2f}%", va="center", ha="left", fontsize=FS_ANNOT,
        )
    ax.set_yticks(y)
    ax.set_yticklabels(order, fontsize=FS_TICK)
    ax.invert_yaxis()
    ax.set_xlabel("Cost saving vs baseline (%)", fontsize=FS_AXIS)
    ax.set_xlim(0, max(sav.max() + 4, 36))
    _style_ticks(ax)

    fig.suptitle(
        "Climate Regime Comparison: Phoenix / Sacramento / Stockholm",
        fontsize=FS_TITLE,
    )

    annot = (
        "Stockholm: free cooling 24/7 → PUE Δ = 0.00 (no thermal lever)\n"
        "Sacramento: blend zone → PUE Δ = 0.022 (workload deferral pays thermal dividend)\n"
        "Phoenix: chiller-bound → PUE Δ = 0.022 but baseline PUE 1.24"
    )
    fig.text(
        0.5, 0.005, annot,
        ha="center", va="bottom", fontsize=FS_ANNOT,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#fdf6e3",
                  edgecolor="#bdc3c7"),
    )

    fig.tight_layout(rect=[0, 0.10, 1, 0.97])
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig4_soc_trajectory(out_path: Path) -> None:
    trace = pd.read_csv(OUTPUTS / "trace.csv")
    soc_df = pd.read_csv(OUTPUTS / "soc_trace.csv")
    config = _load_config()

    bat = config["battery"]
    soc_min = bat["capacity_mwh"] * bat["soc_min_frac"]
    soc_max = bat["capacity_mwh"] * bat["soc_max_frac"]

    h = trace["hour"].to_numpy()
    price = trace["price"].to_numpy()
    p_charge = trace["p_charge"].to_numpy()
    soc = soc_df["soc_mwh"].to_numpy()
    soc_h = soc_df["hour"].to_numpy()
    horizon = int(h[-1] + 1)

    price_p75 = float(np.percentile(price, 75))

    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)

    ax = axes[0]
    ax.step(h, price, where="post", color=COL_PRICE, linewidth=1.4)
    ax.fill_between(h, price, step="post", color=COL_PRICE, alpha=0.20)

    peak_mask = price > price_p75
    in_band = False
    band_start = 0
    label_drawn = False
    for i in range(len(h)):
        if peak_mask[i] and not in_band:
            in_band = True
            band_start = h[i]
        elif not peak_mask[i] and in_band:
            in_band = False
            ax.axvspan(
                band_start, h[i],
                color=COL_BASE, alpha=0.15,
                label="peak price hours" if not label_drawn else None,
            )
            label_drawn = True
    if in_band:
        ax.axvspan(
            band_start, h[-1] + 1,
            color=COL_BASE, alpha=0.15,
            label="peak price hours" if not label_drawn else None,
        )

    ax.set_ylabel("Price ($/MWh)", fontsize=FS_AXIS)
    ax.legend(loc="upper right", fontsize=FS_ANNOT, framealpha=0.9)
    _style_ticks(ax)

    ax = axes[1]
    ax.fill_between(soc_h, soc_min, soc, color=COL_BAT, alpha=0.20)
    ax.plot(soc_h, soc, color=COL_BAT, linewidth=1.8)
    ax.axhline(soc_min, color="black", linestyle="--", linewidth=1.0, alpha=0.6)
    ax.axhline(soc_max, color="black", linestyle="--", linewidth=1.0, alpha=0.6)
    ax.text(horizon - 0.5, soc_min, " SoC_min",
            va="center", ha="left", fontsize=FS_ANNOT)
    ax.text(horizon - 0.5, soc_max, " SoC_max",
            va="center", ha="left", fontsize=FS_ANNOT)

    charging = p_charge > 0.1
    in_band = False
    band_start = 0
    charge_label_drawn = False
    for i in range(len(h)):
        if charging[i] and not in_band:
            in_band = True
            band_start = h[i]
        elif not charging[i] and in_band:
            in_band = False
            ax.axvspan(
                band_start, h[i],
                color=COL_OPT, alpha=0.10,
                label="charging" if not charge_label_drawn else None,
            )
            charge_label_drawn = True
    if in_band:
        ax.axvspan(
            band_start, h[-1] + 1,
            color=COL_OPT, alpha=0.10,
            label="charging" if not charge_label_drawn else None,
        )

    for d in range(1, horizon // 24 + 1):
        x = d * 24
        ax.axvline(x, color="grey", linestyle="-", linewidth=0.7, alpha=0.4)
        axes[0].axvline(x, color="grey", linestyle="-", linewidth=0.7, alpha=0.4)
    for d in range(horizon // 24 + 1):
        x_center = d * 24 + 12
        if x_center < horizon:
            axes[0].text(
                x_center, axes[0].get_ylim()[1] * 0.96,
                f"Day {d + 1}",
                ha="center", va="top", fontsize=FS_ANNOT, color="#566573",
            )

    ax.set_xlabel("Hour of simulation", fontsize=FS_AXIS)
    ax.set_ylabel("Battery SoC (MWh)", fontsize=FS_AXIS)
    ax.legend(loc="upper right", fontsize=FS_ANNOT, framealpha=0.9)
    _style_ticks(ax)
    ax.set_xlim(0, horizon)

    fig.suptitle("Battery SoC Trajectory — 168h (Sacramento)", fontsize=FS_TITLE)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> None:
    PLOTS.mkdir(parents=True, exist_ok=True)
    _ensure_trace()

    figs = [
        ("fig1_dispatch_48h.png",   fig1_dispatch_48h),
        ("fig2_battery_sweep.png",  fig2_battery_sweep),
        ("fig3_geo_comparison.png", fig3_geo_comparison),
        ("fig4_soc_trajectory.png", fig4_soc_trajectory),
    ]
    for name, fn in figs:
        out = PLOTS / name
        fn(out)
        print(f"Wrote: {out}")


if __name__ == "__main__":
    main()
