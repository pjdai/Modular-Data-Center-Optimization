# Modular Data Center — Workload and Battery Optimization

A three-layer linear programming optimizer for a modular data center operating under a constrained grid connection. The model jointly schedules flexible compute workloads, a battery energy storage system, and a weather-driven cooling layer against real-time CAISO prices and WattTime carbon signals.

Developed as a course project for ME 193E / 292E (Next-Generation Data Centers) at UC Berkeley, Spring 2026.

---

## Key Results

Reference scenario: Sacramento, CA — April shoulder season, 168-hour horizon, 4 MWh battery.

| Metric | Baseline | Optimized |
|---|---|---|
| Weekly electricity cost | $45,795 | $30,467 |
| Cost reduction | — | **-33.5%** |
| Grid cap violations (12 MW hard limit) | 2 / 168 h | **0** |
| Grid energy consumed | 1,087.6 MWh | 1,054.4 MWh (-3.1%) |
| Average PUE | 1.147 | 1.125 |

**Battery sizing:** diminishing returns knee at 4 MWh — scaling from 1 to 4 MWh adds +1.69 percentage points of savings; scaling from 4 to 10 MWh adds only +0.29 pp/MWh.

**Geographic sensitivity:**

| City | Climate regime | Avg COP | Cost saving |
|---|---|---|---|
| Sacramento | Blend zone (COP swings 4–20 daily) | 11.9 | 32.75% |
| Phoenix | Chiller-bound (COP ≈ 5.6, no free cooling) | 5.6 | 29.85% |
| Stockholm | Economizer-dominated (COP = 20 always) | 20.0 | 29.95% |

Key finding: **PUE is set by climate, not control.** Stockholm's PUE change = 0.000 because free cooling is always available. Sacramento is the optimal zone for thermal control value.

---

## What makes this different from a standard workload scheduler

Most workload scheduling LP models treat cooling as a fixed overhead (constant PUE). This model adds a **thermal layer** that links IT power directly to cooling power through a climate-dependent COP curve:

$$P_{\text{cooling}} = \frac{P_{\text{IT}}}{\text{COP}(T_{\text{amb}})}$$

The COP model has three regimes:

- $T_{\text{amb}} > 18°C$: mechanical chiller, COP 3–5 (Carnot-limited)
- $T_{\text{amb}} < 10°C$: air-side economizer, COP ≈ 20 (fan affinity laws)
- $10°C \leq T_{\text{amb}} \leq 18°C$: linear blend, COP 4–20

This means the optimizer implicitly times compute to coincide with cool hours — capturing a **thermal dividend** from workload deferral that a pure price or carbon optimizer would miss.

---

## System Configuration

- **IT load:** 500 MW total, four task classes with flexibility windows 0–24 h
- **Grid connection:** 12 MW hard import cap (baseload provides 5 MW constant)
- **Battery:** 4 MWh, 2 MW charge/discharge, 95% round-trip efficiency
- **Optimization horizon:** 168 hours (one week), hourly resolution
- **Solver:** CVXPY / CLARABEL

### Task classes

| Class | Flexibility window | Share | Description |
|---|---|---|---|
| Interactive serving | 0 h | 30% | Live user requests, zero deferral |
| ETL pipeline | 2 h | 20% | Data pipeline jobs |
| Batch ML training | 12 h | 35% | ML training runs |
| Cold backup | 24 h | 15% | Backup and replication |

### Dispatch strategy: the two-trough principle

The optimizer consistently exploits two daily windows:

- **Pre-dawn 3–5 AM:** $T_{\text{amb}} < 10°C$, COP = 20, price ≈ $30/MWh. Maximize compute — both signals favorable.
- **Solar midday 10–14:** CAISO duck curve dip, price $15–22/MWh. Push through rising temperature — price dominates.
- **Evening peak 17–19:** $T_{\text{amb}} = 21°C$, COP = 4, price ≈ $85/MWh. Defer everything flexible — worst dual signal.

---

## Project Structure

```
modular-dc-optimization/
├── run.py                  # Main entry point
├── inputs/
│   ├── config.yaml         # System configuration
│   └── demand_profile.csv  # Hourly demand profile (not tracked)
├── src/
│   ├── optimizer.py        # Joint LP (workload + battery + thermal)
│   ├── baseline.py         # No-optimization reference case
│   ├── sweep.py            # Battery-capacity and geographic sweeps
│   ├── data_loader.py      # CAISO LMP + NOAA weather ingestion
│   └── visualize.py        # Output figures
├── outputs/                # Generated CSVs and plots (not tracked)
├── STATUS.md               # Design decisions and open questions
└── RESULTS.md              # Canonical KPI numbers and narrative
```

---

## Quickstart

```bash
pip install -r requirements.txt
python run.py
```

Output CSVs and plots are written to `outputs/`.

To run the geographic or battery-sizing sweep:

```bash
python src/sweep.py
```

Before running with live data, set your site coordinates in `inputs/config.yaml` and provide API credentials for CAISO and WattTime.

---

## Data Sources

| Signal | Source | Notes |
|---|---|---|
| Locational Marginal Price | CAISO OASIS API | NP15 node, day-ahead |
| Marginal Operating Emissions Rate | WattTime API | Requires account |
| Outdoor air temperature | NOAA / Open-Meteo | Hourly, used for COP |

---

## Dependencies

- CVXPY with CLARABEL solver
- pandas, numpy, matplotlib
- gridstatus (CAISO data ingestion)

See `requirements.txt` for full list.

---

## References

- Radovanovic et al., "Carbon-Aware Computing for Datacenters," IEEE TPS 2023
- Acun et al., "Carbon Explorer," ACM ASPLOS 2023
- Wiesner et al., "Let's Wait Awhile," ACM Middleware 2021
- Verma et al., "Large-scale cluster management at Google with Borg," EuroSys 2015
