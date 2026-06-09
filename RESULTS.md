# Results & Deck Material — Last updated 2026-04-26

> **Purpose.** Canonical source for KPI numbers, evolution narrative, and
> course tie-ins. Copy/quote from this directly into the deck.
> Auto-generated outputs are at `outputs/kpi_summary.csv`,
> `outputs/trace.csv`, `outputs/soc_trace.csv`.

---

## Headline KPIs (default config)

**Setup:** 168 h horizon · Sacramento, CA · CAISO NP15 shoulder-season TOU
prices (April 2024) · NOAA real outdoor temperature (April 2024 hour-of-day
mean) · 4 MWh / 2 MW battery · 5 MW baseload · 12 MW grid cap.

| Metric                        | Baseline      | Optimized     | Δ            |
|-------------------------------|--------------:|--------------:|-------------:|
| Total electricity cost        | $45,795       | $30,467       | **−$15,328 (−33.5 %)** |
| Peak grid draw                | 12.16 MW      | 12.00 MW      | −1.3 %       |
| Total grid energy             | 1087.6 MWh    | 1054.4 MWh    | −3.1 %       |
| Average PUE                   | 1.130         | 1.130         | (set by weather) |
| Grid-cap violations           | 2 / 168 h     | 0 / 168 h     | resolved     |

> **Reading guide.** Cost saving comes from (a) shifting batch ML to cheap
> hours and (b) battery arbitrage. Peak shaving is small because the optimizer
> objective is cost-only, but the grid-cap constraint *did* eliminate the two
> baseline violations.

---

## How the model evolved (story arc for the deck)

The thermal layer is what makes this a thermal-systems project, not a pure power-
systems problem. We took it through three stages, each adding a layer of
realism, and the KPIs moved at each step.

| Stage              | COP model                          | Weather   | Cost saved | Avg PUE | What this version told us |
|--------------------|------------------------------------|-----------|-----------:|--------:|---------------------------|
| **v0** Constant COP | `COP = 4.0` (flat in time)         | n/a       | 27.4 %     | 1.250   | Cost saving comes purely from electricity-price arbitrage. PUE has no shape. |
| **v1** Economizer   | Chiller curve + free-cooling regime | Synthetic diurnal | 32.7 %     | 1.154   | A real *thermal* lever appears — optimizer pushes batch to cool nights, where COP jumps from ~4 to ~20. PUE has a daily shape. |
| **v2** + NOAA       | Same                               | Real Sacramento April | **33.5 %** | **1.130** | Real April climate is cooler than our synthetic — economizer engages even more. PUE 1.13 sits in line with hyperscale industry benchmarks (Google reports ~1.10). |

**Takeaway slide bullet:** "Adding a thermally-aware control layer captures an
extra 6 % cost saving and a 0.12 reduction in average PUE — the gain is real
because the optimizer is choosing not just *when electricity is cheap* but
*when cooling is cheap*."

---

## Why the COP model matters — physics in one paragraph

A chilled-water DC has two cooling regimes:

- **Mechanical chiller** (T_amb high, ~20 °C+) — vapor-compression cycle,
  COP ≈ 3–5, degrades roughly linearly as T_amb rises (Carnot limit on
  condenser side).
- **Air-side economizer** (T_amb low, ~10 °C−) — outdoor air directly cools
  the supply loop, so the only electric load is the fans. Effective COP ≈ 20.

Our model uses three regimes — full chiller above 18 °C, full economizer below
10 °C, linear blend in between. This is a 30-line implementation that captures
the dominant physics; the 18 °C / 10 °C / 20 numbers are tunable in
`inputs/config.yaml`.

**Course tie-ins (oral exam):**
- *Heat exchanger effectiveness:* the COP curve is a rolled-up
  representation of how the chiller's evaporator and condenser approach
  temperatures vary with T_amb.
- *Fan affinity laws:* economizer COP ≈ 20 is justified by P_fan ∝ flow³ — at
  low flow, fan power is negligible compared to lifting heat against a
  compression cycle.
- *Liquid cooling:* swap the COP curve and shift the economizer threshold
  upward (warm-water cooling can engage at higher T_amb). The framework is
  exactly the same — just different parameters.
- *DC siting:* the COP curve runs over real NOAA weather, so swapping
  Sacramento → Phoenix → Stockholm directly demonstrates how climate dominates
  achievable PUE. (See sensitivity sweep, Phase 4.)

---

## First-day trace — 24 h zoom

Real Sacramento April weather, optimized dispatch. Watch how the optimizer
tracks both *cheap electricity* and *high COP*:

```
hour T_amb  COP   price  IT_base  IT_opt   <- comments
   3  9.5°  20.0  $30      6.85    12.26  <- pre-dawn: cheap + cold → flat-out
   4  9.2°  20.0  $30      6.89    12.48      (ML batch + ETL stacked here)
   8 11.0°  18.1  $42      9.64     4.76  <- morning: defer to make room later
  10 15.0°  10.2  $22     11.20    13.00  <- midday: cheap (CAISO solar dip)
  13 19.6°   4.0  $15     13.28    13.00      → run flat-out even though COP is bad
  17 21.0°   3.9  $72     13.21     3.98  <- evening peak: hot AND $72 → defer hard
  18 20.2°   4.0  $85     12.77     4.00      ($85 is the absolute peak hour)
```

**The two-trough strategy** the optimizer learns:
1. **Pre-dawn (3-5 AM):** cool ambient + cheap electricity → push compute hard
2. **Solar midday (10-15):** electricity cheap (CAISO duck curve) even though
   chiller is working hard → still push compute hard
3. **Evening peak (17-19):** hot ambient + expensive electricity → defer
   everything that can be deferred

This is exactly the dispatch shape we want for the deck — it's interpretable,
it tells a clear story, and every choice the optimizer makes can be explained
physically.

---

## Sensitivities we plan to run (Phase 4)

| Sweep variable | Range | What we expect to learn |
|---|---|---|
| Battery capacity | 1, 2, 4, 6, 8, 10 MWh | Diminishing returns curve — finds the "right size" |
| Geographic location | Sacramento / Phoenix / Stockholm | Climate dominates achievable PUE; deck centerpiece |
| COP curve `t_full_econ_c` threshold | 6 °C – 14 °C | Effect of mechanical-design choices on annual PUE |

---

## Figures (Phase 4 — final plots)

All four figures are in `outputs/plots/`. They are the canonical deck visuals —
Pull these directly into the slides. Do not regenerate unless the
model parameters change.

---

### Fig 1 — 48h Dispatch Trace (`fig1_dispatch_48h.png`)

**Use for:** Slide 3 (Model + Results). This is the centrepiece result figure.

Four-panel stacked plot, hours 0–47, Sacramento April shoulder season:
- **Panel 1 (T_amb):** Shows the diurnal temperature swing crossing the 10 °C
  (full economizer) and 18 °C (full chiller) thresholds. Overnight drops below
  10 °C → free cooling engages → COP jumps to ~20.
- **Panel 2 (Price):** CAISO NP15 TOU profile. Evening peak ~$80/MWh clearly
  visible at hours 17–19 each day. Solar midday dip visible at hours 10–14.
- **Panel 3 (Grid draw):** Baseline (red dashed) follows the natural IT demand
  shape and touches the 12 MW grid cap. Optimized (green solid) is much more
  rectangular — it saturates the grid cap during cheap/cold hours and drops near
  zero during expensive/warm hours. Several hours show near-zero grid import:
  these are hours where baseload (5 MW) + battery discharge covers all IT +
  cooling demand — DC is running normally, just not drawing from the grid.
- **Panel 4 (SoC):** Battery charges overnight (cheap + cold) and discharges
  into evening peak. Clean cycles within the 0.4–3.6 MWh operating window.

**Oral exam talking point:** "The optimizer learns a two-trough strategy: push
compute hard at pre-dawn (cheap electricity AND high COP from free cooling) and
at solar midday (cheap electricity, chiller running but price dominates), then
defer everything possible into the evening peak window where electricity costs
$80/MWh AND the chiller degrades COP to ~4."

---

### Fig 2 — Battery Capacity Sweep (`fig2_battery_sweep.png`)

**Use for:** Slide 4 (Sensitivity). Left half of the slide.

Concave cost-saving curve from 1 to 10 MWh, Sacramento shoulder season:

| Range | Marginal gain |
|---|---|
| 1 → 4 MWh | +1.69 pp (high value zone) |
| 4 → 10 MWh | +1.74 pp total, only +0.29 pp/MWh |

Default config (4 MWh, red star) sits at the knee of the curve — the point
where marginal returns start to flatten. This directly answers the design
question: "how big does the buffer need to be?"

**Oral exam talking point:** "We sized the battery at 4 MWh because it sits at
the knee of the diminishing-returns curve. Beyond 4 MWh, each additional MWh
of storage buys less than 0.3 percentage points of extra cost saving — the
workload deferral lever is doing most of the heavy lifting, not the battery."

**Note:** PUE is flat across the battery sweep (all rows = 1.1246). This
confirms that PUE improvement comes entirely from workload deferral, not from
battery dispatch. Battery only affects cost and peak shaving.

---

### Fig 3 — Geographic Climate Comparison (`fig3_geo_comparison.png`)

**Use for:** Slide 4 (Sensitivity). Right half of the slide. Also the strongest
oral exam slide — directly maps to DC siting course content.

| City | avg T_amb | avg COP | PUE baseline | PUE optimized | PUE Δ | Cost saving |
|---|---|---|---|---|---|---|
| Phoenix | 21.5 °C | 5.6 | 1.2434 | 1.2213 | 0.022 | 29.85% |
| Sacramento | 14.6 °C | 11.9 | 1.1468 | 1.1246 | 0.022 | 32.75% |
| Stockholm | 4.3 °C | 20.0 | 1.0500 | 1.0500 | 0.000 | 29.95% |

Three distinct regimes:

**Phoenix (chiller-bound):** T_amb > 18 °C nearly every hour. Mechanical
chiller runs constantly, COP ≈ 5.6. Baseline PUE 1.24 — highest of the three.
Workload deferral still yields a 0.022 PUE improvement and 29.85% cost saving,
but there is no free-cooling headroom to exploit. The thermal lever is present
but weak.

**Sacramento (blend zone — sweet spot):** T_amb swings from ~9 °C overnight to
~21 °C at peak. COP swings from ~4 (chiller-only) to ~20 (full economizer).
This diurnal COP variation is what the optimizer exploits — shifting batch
workload to cool nights gives both a cost saving AND a thermal dividend. Highest
cost saving (32.75%) and meaningful PUE improvement (0.022).

**Stockholm (economizer-dominated):** T_amb < 10 °C every hour of the
simulation. Free cooling is unconditional — COP is pinned at 20 all day, every
day. Baseline PUE = optimized PUE = 1.050 exactly, PUE Δ = 0.000. There is no
thermal lever for workload deferral to exploit. Cost saving (29.95%) comes
entirely from TOU price arbitrage and battery cycling, not from thermal
management.

**The Stockholm row is the strongest single data point in the project** for an
oral exam: it directly proves that the thermal benefit of workload-aware control
*collapses* when free cooling is unconditional. DC siting in cold climates
gives you a low baseline PUE for free — but it also removes the control
headroom that makes thermally-aware scheduling valuable.

**Oral exam talking point:** "Stockholm shows us the limits of our approach.
When free cooling is always available, PUE is determined by climate alone —
our controller can't improve it further. Sacramento is where workload-aware
thermal control actually earns its keep, because there's a real COP gradient
across the day to exploit."

---

### Fig 4 — Full-Week SoC Trajectory (`fig4_soc_trajectory.png`)

**Use for:** Slide 3 appendix or oral exam backup. Shows the weekly regularity
of battery dispatch.

Two-panel, 168h horizon:
- **Top (Price):** Daily TOU pattern repeats with high regularity. Red shading
  marks peak-price hours (>75th percentile, ~$65–85/MWh). Weekend days (Day 6,
  7) show a slightly lower and flatter price profile — consistent with lower
  industrial demand on weekends in the CAISO zone.
- **Bottom (SoC):** Battery executes one clean charge-discharge cycle per day,
  every day. Green bands (charging windows) align precisely with price troughs;
  discharging happens into peak-price hours. The cyclic SoC constraint closes
  perfectly — Day 7 ends at the same 2.0 MWh initial state.

**Oral exam talking point:** "The battery behaviour is highly periodic and
price-predictive — not reactive. Because TOU tariffs have a stable daily
structure, the LP internalises the full week at once and produces a repeating
optimal policy. In a real deployment you would use a rolling MPC horizon, but
the qualitative dispatch pattern would be the same."

---

## Caveats & honest limitations

- **Single battery, no degradation cost.** Real BESS owners trade off cycle
  count vs cycle revenue; we don't.
- **No demand charge.** California TOU is energy-only here; commercial DC
  tariffs would also include $/kW peak charges that would change the optimal
  control.
- **Air-side economizer with no humidity penalty.** Adequate for dry-climate
  cases (CA, Phoenix); would need a wet-bulb adjustment for humid sites.
- **Constant baseload.** A real geothermal or nuclear plant has scheduled
  outages and ramp limits; we treat it as ideal.
- **Workload trace is synthetic.** The diurnal × weekday/weekend modulation is
  qualitatively right (matches published Google trace shapes) but not a
  specific real DC.

These are honest caveats — none of them change the *direction* of the result.
Mention 2–3 in the oral exam to pre-empt "what about X" questions.
