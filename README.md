# Modular Data Center — Workload + Battery Optimization

Workload-aware scheduling and battery buffer optimization for a modular data center
powered by a fixed-capacity baseload source under a constrained grid connection.

See `STATUS.md` for current status and open decisions, and `RESULTS.md` for the
KPI tables and deck-ready talking points.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python run.py
```

This will:
1. Generate (or reuse) a 168 h synthetic workload trace
2. Fetch (or fall back to cached) CAISO TOU prices → `inputs/energy_cost.csv`
3. Fetch (or fall back to cached) outdoor temperature for the configured
   location via Open-Meteo → `inputs/outdoor_temp.csv`
4. Run the no-control baseline
5. Solve the joint workload-deferral + battery-dispatch LP with a time-varying
   COP curve driven by real outdoor temperature
6. Print KPIs and write `outputs/trace.csv`, `outputs/soc_trace.csv`, `outputs/kpi_summary.csv`

Note: `gridstatus` is disabled in `requirements.txt` because its transitive
dep `lxml` has no Python 3.14 wheel. The fallback CAISO LMP profile is
used instead. Weather uses Open-Meteo (stdlib `urllib`, no extra deps).

## Project Layout

```
.
├── STATUS.md                ← where we are + open decisions
├── RESULTS.md               ← KPI tables + deck-ready talking points
├── run.py                   ← main entry point
├── inputs/
│   ├── config.yaml          ← all tunable parameters
│   ├── energy_cost.csv      ← cached CAISO LMP (built on first run)
│   ├── outdoor_temp.csv     ← cached weather (built on first run)
│   └── demand_profile.csv   ← cached synthetic workload trace
├── src/
│   ├── data_loader.py       ← CAISO LMP + Open-Meteo loaders, both with fallback
│   ├── workload.py          ← synthetic IT trace generator
│   ├── battery.py           ← SoC dynamics + cvxpy vars
│   ├── thermal.py           ← COP model (constant or chiller+economizer) + PUE
│   ├── baseline.py          ← no-control counterfactual
│   ├── optimizer.py         ← joint LP (workload + battery + thermal)
│   ├── sweep.py             ← battery-capacity + geographic sweeps
│   └── visualize.py         ← four publication figures
└── outputs/
    ├── trace.csv            ← hourly time series, both scenarios
    ├── soc_trace.csv        ← battery state of charge
    ├── kpi_summary.csv      ← scalar KPIs
    ├── sweep_battery.csv    ← battery-size sweep
    ├── sweep_geo.csv        ← geographic sweep
    └── plots/               ← PNG plots
```

## Status

Phases 1–4 complete. Headline KPI under default config (Sacramento April, 168 h):
**−33.5 % electricity cost** vs no-control baseline · avg PUE 1.13.

See `STATUS.md` for the full status and open decisions, and `RESULTS.md` for the
deck-ready talking points.
