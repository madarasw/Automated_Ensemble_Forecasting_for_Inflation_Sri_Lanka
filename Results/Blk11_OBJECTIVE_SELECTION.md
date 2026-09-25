# Block 1.1 — Which fitting objective to carry into Blocks 2–5

**Decision record for gate P1-08 (metric selection rule).**
Prepared 2026-09-24 from `Results/Results_Blk11_MetricSearch.xlsx` (306/306 runs complete).

---

## 1. Recommendation

| | Objective | AutoGluon `eval_metric` |
|---|---|---|
| **Primary — carry into Blocks 2–5** | **EM9 — WQL** (weighted quantile loss) | `"WQL"` |
| Statistically interchangeable alternates | EM11 MQL, EM10 SQL | `"MQL"`, `"SQL"` |
| Contrast arm — keep for the paper's central claim | EM2 MAE, EM3 RMSE, EM12 DTW | — |
| **Drop as fitting objectives** (keep as *reported* metrics) | EM15 TDI, EM18 TPA, EM16 TDA | — |

**One objective answers both questions the study poses.** The quantile-loss family
is simultaneously (a) tied for the most accurate point forecast and (b) decisively
the best-calibrated narrow interval. Nothing else is on both lists.

---

## 2. Experimental base

Balanced and complete: **3 CPI targets × 17 candidate objectives × 6 origins = 306 runs**,
no failures, no missing actuals.

| Setting | Value |
|---|---|
| Targets | HCPI, FCPI, CCPI (Colombo) |
| Origins | 2025-04 … 2025-09 (last six available) |
| Window | 124 periods training, 24 held for internal validation |
| Horizon | 12 months, index level |
| `refit_full` | **False** |
| Pretrained models | **Included** (Chronos, Chronos-Bolt, Chronos-2) |
| Runtime | 264–308 s per run; **flat across objectives** — cost is not a tiebreaker |

Each objective therefore has 18 paired observations (3 targets × 6 origins).
All comparisons below are **paired within a target-origin cell**, so a cell's
intrinsic difficulty cancels.

---

## 3. Question 1 — which objective gets closest to the actual index?

Measured as MAE on the index level, divided by the median objective's MAE in the
same cell. Below 1.000 = better than a typical objective.

| Objective | All | HCPI | FCPI | CCPI | Mean rank /17 | Worst cell MAE |
|---|---|---|---|---|---|---|
| **MQL (EM11)** | **0.842** | 0.787 | 0.844 | 0.944 | 5.92 | **6.06** |
| **SQL (EM10)** | 0.847 | 0.790 | 0.831 | 0.945 | 6.50 | 6.07 |
| **WQL (EM9)** | 0.853 | 0.785 | 0.851 | 0.945 | 6.03 | **6.06** |
| SoftDTW (EM13) | 0.870 | 0.819 | **1.041** | 0.793 | 6.28 | 11.23 |
| DTW (EM12) | 0.886 | 0.777 | **1.054** | 0.731 | 5.67 | 8.27 |
| RMSE (EM3) | 1.000 | 1.000 | 1.151 | 0.984 | 8.97 | 10.65 |
| MAE (EM2) | 1.015 | 1.034 | 1.000 | 1.179 | 10.28 | 9.11 |
| TDI (EM15) | 1.318 | 1.423 | 2.068 | 0.922 | 11.44 | 8.33 |
| TPA (EM18) | 1.658 | 13.802 | 1.221 | 1.622 | 13.56 | 83.58 |

**Read carefully — this is the one place where mean rank misleads.**
DTW has the best mean rank (5.67), so a naive reading would pick it. But DTW is
*worse than a typical objective on FCPI* (1.054). Its strong average comes from
being excellent on HCPI and CCPI and poor on the third target. The quantile family
is the only group that is **below 1.000 on all three targets**.

Robustness confirms it: the quantile family's **worst single cell** is MAE 6.06,
against 8.27 for DTW, 9.11 for MAE and 10.65 for RMSE. For a central-bank
publication the worst case matters more than the average.

**Statistically:** Friedman χ² = 57.3 (df 16) — the objectives genuinely differ.
But in a pairwise sign-flip permutation test with Holm correction, **the top five
(DTW, MQL, WQL, SQL, SoftDTW) cannot be separated from one another**. The classic
point metrics are 18–33% worse on average (raw p ≈ 0.03–0.09, not surviving Holm
across 16 comparisons). With 18 cells there is simply not enough power to split
the leaders on point accuracy alone.

**So point accuracy alone does not decide this. Question 2 does.**

---

## 4. Question 2 — which objective gives the best narrow interval?

| Objective | 80% band width (% of level) | Actual coverage | Winkler score | Pinball |
|---|---|---|---|---|
| **MQL (EM11)** | **9.43** | 0.954 | **9.75** | **0.748** |
| **SQL (EM10)** | 9.46 | 0.944 | 9.78 | 0.755 |
| **WQL (EM9)** | 9.48 | 0.949 | 9.80 | 0.753 |
| DTW (EM12) | 11.90 | 0.986 | 11.99 | 0.823 |
| SoftDTW (EM13) | 12.27 | 0.977 | 12.40 | 0.882 |
| MAPE (EM4) | 13.00 | 0.954 | 13.73 | 0.992 |
| MAE (EM2) | 13.27 | 0.986 | 13.29 | 0.971 |
| RMSE (EM3) | 14.26 | 0.986 | 14.31 | 1.000 |
| DA (EM17) | 16.55 | 0.810 | 30.93 | 2.105 |
| TDA (EM16) | 19.78 | 0.977 | 19.98 | 1.227 |
| TPA (EM18) | 31.61 | **0.699** | 38.15 | 4.728 |
| TDI (EM15) | 32.13 | 1.000 | 32.13 | 1.748 |

*Nominal coverage is 0.80. Winkler = interval score at 80%, as % of level; lower is better.*

This is where the evidence is decisive. Friedman χ² = **118.6** — twice the point-accuracy
statistic. In the Holm-corrected pairwise test against MQL:

- **MQL, WQL and SQL are indistinguishable from each other** (p_holm = 0.18)
- **Every other objective is significantly worse**, all p_holm ≤ 0.003:
  DTW +20.5%, SoftDTW +23.2%, MASE/MAE/WAPE +33–34%, SMAPE/Wasserstein/MAPE +36–37%,
  RMSSE/RMSE +40%, TDA +84%, DA +100%, TPA +193%, TDI +231%.

**The narrowness is honest, not bought by under-covering.** Three checks:

1. For the leaders the Winkler score is **97% width and only 3% miss-penalty** — so
   "best interval score" here really does mean "narrowest band".
2. The quantile family still covers **95.4% of outturns at a nominal 80%**. It is the
   narrowest *and* still conservative.
3. Its 90th-percentile width is 10.8% of level, against 15.7% (DTW) and 17.7% (MAE) —
   it does not blow out in the hard cells.

Contrast with the two objectives that produce genuinely narrow-but-wrong bands:
DA (EM17) has the coverage closest to nominal (0.810) but a Winkler score of 30.9,
because **46% of its score is miss-penalty** — it is narrow in the wrong places.
TPA (EM18) under-covers outright (0.699).

---

## 5. Choosing within the quantile family

WQL, SQL and MQL are three normalisations of the same pinball loss, and the runs
confirm they are the same objective in practice:

- Mean total-variation distance between their ensemble weight vectors: **0.013–0.023**
  (the average across all 136 objective pairs is **0.616**).
- They select the same models in the same proportions:
  Naive 0.40 · Chronos-2 0.30 · AutoCES 0.17 · Theta 0.05.

MQL is nominally first on both criteria, but it beats WQL in only 7 of 18 cells on
interval score — that is a coin flip, not a finding.

**Use WQL (EM9)** on non-statistical grounds: it is AutoGluon's own default, it is
the standard weighted quantile loss in the forecasting literature, it is scale-free
across the three targets, and it is the one a referee will recognise without
explanation. Record in the paper that MQL and SQL were statistically
indistinguishable from it.

---

## 6. Objectives to drop as fitting targets

Ensemble degeneracy, measured as the effective number of models
(inverse Herfindahl of the weight vector):

| Objective | Effective models | Runs collapsed to one model (of 18) |
|---|---|---|
| DTW | 3.23 | 0 |
| RMSE | 2.97 | 0 |
| MAE | 2.55 | 0 |
| WQL / SQL / MQL | 2.11–2.14 | 3 |
| DA (EM17) | 1.85 | 4 |
| **TDA (EM16)** | 1.26 | **11** |
| **TDI (EM15)** | 1.00 | **18** |
| **TPA (EM18)** | 1.00 | **18** |

TDI and TPA collapse to a single model in **every** run; TDA in 11 of 18. These
objectives take only a handful of discrete values over a 12-point horizon, so
greedy forward ensemble selection sees ties everywhere and keeps whichever model
it happened to try first. Their forecasts are arbitrary, not optimised.

**Keep all 18 metrics in the *reporting* set** — showing that these objectives fail
is part of the paper's contribution. Stop using them as *fitting* objectives in
Blocks 2–5. Dropping TDI, TPA and TDA removes 3 of 17 arms, about 18% of the
remaining compute, with no loss of information.

---

## 7. Three findings that belong in the manuscript

**7.1 Fitting on the level or on YoY does not change the ranking.**
The objective ranking is identical in **18 of 18 cells** whether errors are scored
on the index level or on the YoY inflation rate (Spearman 0.987 across all 306
cells). The reason is arithmetic: YoY error at month *t* equals level error divided
by the actual index 12 months earlier, and that divisor barely moves within a
12-month horizon, so YoY MAE is a near-constant rescaling of level MAE. The earlier
design decision to forecast the level and convert afterwards is therefore harmless
for metric selection.

**7.2 Every objective's intervals are too wide.** Nominal 80% bands contain
94–99% of outturns across the whole candidate set. The quantile family is the
least over-wide and is still at 95%. This is a property of AutoGluon's quantile
estimation on this data, not of the objective choice, and it argues for a post-hoc
interval recalibration step before the paper reports coverage.

**7.3 The winning ensemble is 40% Naive and 30% Chronos-2.** Over a 12-month
horizon on these series the quantile objective concludes that a random walk plus a
foundation model is hard to beat. Both halves of that need discussing — the Naive
weight speaks to the forecastability limit, and the Chronos-2 weight sits directly
on the pretraining-contamination question, since Chronos-2's release date
straddles these origins.

A fourth, smaller point: most objectives **under-forecast** by about 0.9–1.0% of
the index level. DTW (−0.43), Wasserstein (−0.17) and SoftDTW (−0.06) are the
least biased. If bias is a reported quantity, note that the recommended objective
is not the least biased one.

---

## 8. What this does *not* establish

1. **One regime only.** All six origins fall in 2025-04 … 2025-09. The 124-period
   window cannot reach regimes R1–R4. This selects an objective for a stable,
   post-stabilisation period and says nothing about crisis behaviour.
2. **Selection and evaluation share the same origins.** The confirm round on the
   full 69-origin set is still required before the choice is final. Leave-one-out
   is reassuring but not a substitute: dropping any one target or any one origin,
   the interval-quality winner is MQL or WQL in **9 of 9 folds**; the point-accuracy
   winner alternates between DTW, MQL and WQL, which is the tie restated.
3. **Six origins per cell is low power.** It is enough to separate the quantile
   family from the rest on interval quality (χ² = 118.6) and not enough to separate
   the top five on point accuracy. Do not report the point-accuracy ordering within
   the leading group as a result.
4. `refit_full = False` throughout. Block 0 is still needed to pair against the
   archived `refit_full = True` arm.

---

## 9. Files

| File | Contents |
|---|---|
| `Results/Analysis/blk11_objective_summary.csv` | one row per objective — every number quoted above |
| `Results/Analysis/blk11_cells.csv` | all 306 cells — point, interval, coverage, bias |
| `Results/Figures/fig_blk11_objective_selection.png` | two-panel summary figure |
| `Results/Figures/fig_blk11_objective_selection.csv` | that figure's plotted values |

To apply the decision, set the fitting objective for Blocks 2–5 to `"WQL"` and
remove EM15, EM16 and EM18 from the fitting arm of `Code/experiments.csv`.

---

## 10. Consequential decision — Block 2.1 revised, per-variable objectives (2026-09-24)

Block 2.1 has been repurposed to carry the origin extension, and the fitting objectives are
now **chosen separately for each target, ranked on YoY accuracy** (mean absolute gap between
forecast YoY and actual YoY, in percentage points, over all 72 forecast months in Block 1.1).

| | Before | After |
|---|---|---|
| Objective | `EM1` (single, unresolved) | **top 3 per variable, by YoY accuracy** |
| Origins | o58-o69 (12) | **o53-o63 (11)** |
| Runs | 36 | **99** |

### Selected objectives

| Target | Objectives | mean \|YoY gap\| (pp) |
|---|---|---|
| **HCPI** | DTW (EM12) · MQL (EM11) · Soft-DTW (EM13) | 1.427 · 1.536 · 1.712 |
| **FCPI** | MQL (EM11) · MAPE (EM4) · MAE (EM2) | 1.503 · 2.095 · 2.150 |
| **CCPI** | DTW (EM12) · Soft-DTW (EM13) · Wasserstein (EM14) | 1.848 · 1.974 · 2.324 |

Six distinct objectives across the three targets; 33 runs each.

### Three documented departures from a mechanical top-3

1. **WQL/SQL/MQL collapsed to one representative.** They are three normalisations of the
   same pinball loss (mean total-variation distance between their ensembles 0.013-0.023,
   against 0.616 across all pairs). A literal top 3 would have been *all three of them* for
   FCPI and two of them for HCPI, wasting most of that variable's compute on one objective.
   MQL is taken as the representative — it is nominally first of the three on all three
   targets.
2. **TDA (EM16) excluded from CCPI despite ranking 3rd** (2.134 pp). It collapses to a
   single model in 3 of its 6 CCPI runs (effective models 1.35), so it is not an ensemble
   result. Wasserstein, 4th at 2.324 with 2.81 effective models and no collapses, takes the
   slot.
3. **MAE kept for FCPI in place of WAPE.** FCPI's 4th-8th places are a statistical dead
   heat — MAPE 2.095 to MAE 2.150, a 0.055 pp spread at p = 1.00 on a sign-flip test. MAE
   costs nothing against that plateau and preserves the practitioner-default control, which
   the paper's "objective choice matters" claim is measured against.

### What this buys

o64-o69 from Block 1.1 plus o53-o63 here give the complete **17 origins**, every origin a
124-month window can reach on HCPI and FCPI. The plan's own labels put o53-o60 in **R5
(Deflation & stabilisation)** and o61-o63 in R6; Block 1.1's six origins were all R6, so 72
of the 99 new runs are the first at this window outside R6 — the objective choice can be
tested across a regime boundary rather than inside one.

### Left deliberately untouched

1. **The 441 `BL-M-*` baseline rows**, 36 of which carry `block == "2.1"` but belong to
   `Blk5_Baselines`. Filtering on `block == "2.1"` alone destroys them. Their origins
   (o58-o69) no longer align with Block 2.1's — decide separately whether the baseline arm
   follows to o53-o63.
2. **Blocks 2.2 (Quarterly, 22 runs, window 40) and 2.3 (Annual, 7 runs, window 10)**,
   which share the `Blk2_Selected_PreOn` tab. This monthly work covers neither.
3. **`Code/common/experiment.py`** — controls stay frozen.

### Caveat for the manuscript

These objectives were selected on 6 origins in a single regime, and are now being run on 11
more. Report the 11 new origins as an out-of-sample confirmation before pooling all 17;
adjacent monthly origins share 11 of their 12 forecast months, so 17 origins span 28 months
of outcomes and roughly 2.3 independent horizons, not 17.

Recorded in `Code/experiments.csv` (1,275 rows) and in the `Blk2_Selected_PreOn` and
`MASTER` sheets of `Main_Experiment_Plan.xlsx`.

---

## 11. Baseline set extended before Block 4.1 (2026-09-25)

`Code/common/baselines.py` previously offered **seasonal-naive and ARIMA only**, and the
ARIMA grid searches p,d,q in {0,1,2} *excluding p=q=0* - so ARIMA(0,1,0), a plain random
walk, was never a candidate, only a convergence fallback. The random walk was therefore
absent from the comparison set entirely.

That matters because on a 17-origin check of this study's own results the random walk is
by far the strongest simple benchmark, and it beats the fitted ensembles on two of three
targets:

| Benchmark | mean \|YoY error\| | within 2% |
|---|---|---|
| **Random walk (repeat last value)** | **1.76 pp** | 67.0% |
| RW with drift (trailing 12-month) | 2.25 pp | 48.7% |
| Seasonal naive | 2.29 pp | 43.5% |
| Atkeson-Ohanian | 2.81 pp | 39.7% |

Per target, mean \|YoY error\|: FCPI MQL 1.68 vs RW 2.18 (**model wins, +22.9% skill**);
HCPI DTW 1.51 vs RW 1.55 (**tie**); CCPI Soft-DTW 1.69 vs RW 1.54 (**RW wins, -9.8%**).
Comparing only against seasonal-naive would have reported comfortable skill everywhere
and been wrong.

Three functions were added - `naive_forecast`, `drift_forecast`,
`atkeson_ohanian_forecast` - and wired into `run_baselines`, which now also returns
`naive_*`, `drift_*` and `atkeson_ohanian_*` keys. Existing keys are unchanged, so
`Tab22_Baselines.py` is unaffected. All three were verified against an independent
reconstruction on all 612 forecast points (3 targets x 17 origins x 12 months): maximum
absolute difference 5.7e-14.

Two conventions are documented in the module and must be quoted if the numbers are
reported: drift uses the **trailing 12-month** average change, not the full-sample
slope; Atkeson-Ohanian is seasonal-naive scaled by the latest year-on-year rate.

### Still blocking Block 4.1

`EM1` is a placeholder and is **not** in the metric registry (`ALL_EM_CODES` covers
EM2-EM18 only), so `resolve_eval_metric("EM1", ...)` raises `ValueError` and every one of
Block 4.1's 207 model rows would fail on the first call. EM1 must be substituted with
real codes before that block can run. Recommended, from the per-variable selection
confirmed out of sample on the 11 Block 2.1 origins:

| Target | EM1 resolves to | mean \|YoY err\| on the 11 out-of-sample origins |
|---|---|---|
| HCPI | **EM12 (DTW)** | 1.56 pp (vs Soft-DTW 1.64, MQL 1.73) |
| FCPI | **EM11 (MQL)** | 1.78 pp (vs MAE 2.43, MAPE 2.49) |
| CCPI | **EM13 (Soft-DTW)** | 1.53 pp (vs Wasserstein 1.67, DTW 1.78) |

Caveat to document: those objectives were selected at a 124-month window with pretrained
models enabled. Block 4.1 is a 72-month window with pretrained models disabled, so the
transfer is an assumption, not a result.
