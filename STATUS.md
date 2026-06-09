# Project Status — Last updated 2026-04-26

> **Status & open decisions.** Where we are, and what still needs to be decided.

---

## TL;DR

We have a working end-to-end model. `python run.py` produces baseline-vs-
optimized KPIs in ~10 seconds. Phases 1, 2, 3 are done. We're entering Phase 4
(sensitivity sweeps + plots), then Phase 5 (deck).

**Headline numbers under default config (Sacramento, shoulder season, real NOAA
weather, 168 h horizon):**

| Metric                | Baseline | Optimized | Saving |
|-----------------------|---------:|----------:|-------:|
| Total electricity cost | $45,795 | $30,467   | **−33.5 %** |
| Peak grid draw         | 12.16 MW | 12.00 MW | −1.3 %  |
| Total grid energy      | 1087.6 MWh | 1054.4 MWh | −3.1 % |
| Average PUE            | 1.130   | 1.130     | (same — PUE is set by weather, not control) |

Detailed numbers + the "what changed at each phase" story are in `RESULTS.md`.

---

## What you can read without running anything

- `STATUS.md` — this file.
- `RESULTS.md` — current KPI tables, headline plots (once we generate them),
  and the talking points for the deck.
- `outputs/kpi_summary.csv` — machine-readable KPI table.
- `outputs/trace.csv` — hourly trace: T_amb, COP, price, P_IT, P_grid,
  battery charge/discharge. Open it in Excel/Numbers and you can scroll through
  the whole week.
- `outputs/soc_trace.csv` — battery state-of-charge trajectory.

---

## What's done

| Phase | Status | What changed |
|---|---|---|
| **1. Skeleton & Baseline** | ✅ | Workload, prices, battery, no-control baseline all wired up |
| **2. Joint optimization** | ✅ | LP solves, ~33 % cost saving, fair comparison vs baseline |
| **3. Thermal layer** | ✅ | Upgraded from "constant COP" stretch goal to **temperature-dependent COP with air-side economizer**, fed by **real NOAA weather** for Sacramento. PUE is now time-varying — story we can actually tell. |
| **4. Sensitivity & polish** | ✅ | Plots and sweeps not done yet |
| **5. Deck & oral prep** | 🔄 in progress | Your turn once Phase 4 lands |

---

## Open decisions — your input needed

What I'd like from you:

1. **Pitch horizon.** 168 h trace with a 48 h zoom panel, or 48 h only?
   *Proposed:* 168 h to show the weekly weekend dip + a 48 h zoom panel for
   readability of the dispatch trace. Two figures, not one.

2. **Geographic sensitivity sweep — which 3 cities?**
   The thermal model now reads NOAA weather. Changing `outdoor_temp.noaa.{lat,lon}`
   in `inputs/config.yaml` and re-running `run.py` is a 1-line change that gives
   us a "DC siting" story directly aligned with course content.
   *Proposed:* Sacramento (have it) + **Phoenix** (hot, chiller-bound) +
   **Stockholm** (cold, free-cooling-dominated). Skip humid (Singapore) — adds
   complexity we'd have to model latent loads for.

3. **Battery sweep range and step size.**
   We sweep battery capacity to answer "how big does the buffer need to be?"
   *Proposed:* 1, 2, 4, 6, 8, 10 MWh — six points, linear. Default config
   sits at 4 MWh, so the sweep brackets it.

4. **Prior case-study callback.**
   Worth a dedicated slide, or only mention verbally if asked? It's the
   strongest content tie-in we haven't used yet.

5. **Anything you want to *add* to the model?**
   Easy wins still on the table: humidity-dependent cooling, liquid-cooling
   comparison curve, time-of-day demand-charge tariff.

Just answer 1–4 in any format (Slack, email, comments below) and I'll run the
sweeps.

---

## Environment notes

- **Python 3.14.** All deps install fine *except* `gridstatus` (transitive
  `lxml` has no 3.14 wheel). Disabled in `requirements.txt` with a comment;
  doesn't matter because we use the **Open-Meteo API** for weather (no key
  needed) and the **fallback CAISO LMP profile** for prices.
- **First run** of `python run.py` fetches ~30 days of Sacramento weather
  from Open-Meteo (~5 sec) and caches to `inputs/outdoor_temp.csv`. Subsequent
  runs read the cache. Same pattern as `inputs/energy_cost.csv`.
- If you need to install: `pip install -r requirements.txt` after cloning.
  Don't try to enable `gridstatus` on Python 3.14 — it'll fail to build `lxml`
  (we hit this; documented in the requirements.txt comment).

---

## Quick reference — where to change what

| If you want to … | Edit this file |
|---|---|
| Change battery size / efficiency | `inputs/config.yaml` → `battery:` |
| Change grid cap or baseload | `inputs/config.yaml` → `supply:` |
| Change weather location (Phoenix etc.) | `inputs/config.yaml` → `thermal.outdoor_temp.noaa:` (then **delete `inputs/outdoor_temp.csv`** so it re-fetches) |
| Change task mix (workload deferral flexibility) | `inputs/config.yaml` → `tasks:` |
| Switch back to constant COP for sanity check | `inputs/config.yaml` → `thermal.cop_model: constant` |
| Change horizon (168 h ↔ 24 h) | `inputs/config.yaml` → `horizon_hours:` |

No code changes needed for any scenario sweep — it's all config-driven.
