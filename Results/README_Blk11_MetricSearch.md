# Block 1.1 — Metric Search: what was run and how to read the results

Prepared for the paper author. Everything needed to interpret
`Results_Blk11_MetricSearch.xlsx` is here; no prior context assumed.

---

## 1. What the study is

Benchmarking an automated ensemble forecaster (AutoGluon-TimeSeries) on Sri Lankan inflation.
Rather than pick one model, the framework fits many and combines them into a weighted ensemble.
The research interest is **interpretability**: how the ensemble's weights shift across inflation
measures, data frequencies, economic regimes, and — the subject of this block — **the evaluation
metric used as the ensemble's fitting objective**.

Three forecast targets, all published by Sri Lanka's Department of Census and Statistics, all
index levels on 2021=100:

| Code | Series |
|---|---|
| `HCPI` | Headline / all items = the **National** CPI (NCPI) |
| `FCPI` | NCPI **food** group |
| `CCPI` | **Colombo** CPI, all items |

> **Naming warning.** `CCPI` here means the **Colombo** CPI, following Sri Lankan convention.
> The submitted abstract used `CCPI` for *Core* CPI and also promised an energy index (`ECPI`),
> which was dropped because no publisher issues one for Sri Lanka. See `INDEX_SET_CHANGE.md` in
> the repository root — these deviations must be stated in the paper.

---

## 2. What Block 1.1 is for

The evaluation metric is not only how forecasts are scored — it is the **objective AutoGluon
optimises when it decides the ensemble weights**. Change the objective and you change which
models get weight. So "which metric gives the most meaningful assessment of forecast quality for
Sri Lankan inflation?" is a research question, not a formatting choice.

Block 1.1 runs the **same forecasts 17 times**, once per candidate fitting objective, holding
everything else fixed. Any difference in the ensemble weights is therefore attributable to the
metric and nothing else.

The 17 candidates:

| Codes | Family | Metrics |
|---|---|---|
| EM2–EM8 | Point accuracy | MAE, RMSE, MAPE, sMAPE, MASE, RMSSE, WAPE |
| EM9–EM11 | Proper scoring rules | WQL, SQL, MQL |
| EM12–EM15 | Temporal similarity | DTW, Soft-DTW, Wasserstein, TDI |
| EM16–EM18 | Directional | TDA, DA, TPA |

The winner becomes **EM1**, the metric used for every later block. It has **not** been chosen
yet, and the selection rule is still open (see §8).

---

## 3. Design of this block

| | |
|---|---|
| Variables | HCPI, FCPI, CCPI |
| Frequency | Monthly only |
| Origins | the **last 6** — o64 to o69, horizons starting Apr–Sep 2025 |
| Forecast horizon | 12 months |
| Training window | **100 + 24 = 124 months**, fixed and rolling |
| Validation | 24 months (`num_val_windows = 2`) |
| Model pool | highest-quality preset **including** the pretrained Chronos family |
| `refit_full` | False |
| `time_limit` | 900 s per fit |
| Random seed | 123 |
| Target | index level, 2021=100 |
| Total | 3 × 17 × 6 = **306 runs** |

**Rolling-origin rule.** Training ends the month immediately before the horizon begins — no gap,
no overlap. Each run trains on exactly 124 months and forecasts the next 12. Origin o64 trains
Dec 2014 – Mar 2025 and forecasts Apr 2025 – Mar 2026.

### Two limitations of this block that belong in the paper

1. **All six origins fall in regime R6 (post-stabilisation).** This is not a choice. A
   124-month window only exists from May 2024 onward for HCPI and FCPI, so the block physically
   cannot reach the 2022 crisis. **EM1 is therefore selected on calm-period evidence.**
2. **EM1 is selected on monthly data and applied to quarterly and annual too.** The quarterly
   and annual metric searches were dropped — ranking 17 candidates on 4 and 2 origins cannot
   separate them.

---

## 4. Files

| File | What it is |
|---|---|
| `Results/Results_Blk11_MetricSearch.xlsx` | **the results** — one sheet per run |
| `Results/RunConfigs/Blk11_MetricSearch/*.json` | machine-readable provenance, one per run |
| `Results/PROGRESS.md` | live completion counter |
| `Code/experiments.csv` | the full design — every row is one planned run |
| `Data/final_data.csv` | the input series |
| `Data/methodology_data_collection.md` | where the data came from and how it was validated |
| `INDEX_SET_CHANGE.md` | deviations from the submitted abstract |

---

## 5. Reading a results sheet

One sheet per run, named by `exp_id` (`B11-M-001` … `B11-M-306`). To find which run is which,
join `exp_id` against `Code/experiments.csv`, or read the header block. Each sheet has four
sections.

### 5.1 Header — rows 1–31

Key/value provenance: which variable, which metric was the fitting objective, the exact training
window and horizon, the model actually deployed, runtime, GPU, AutoGluon version, seed, and
every control setting. `train_rows_actual` confirms the window really was 124 rows.

### 5.2 Forecast table — from row 34

```
date | mean | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 | actual
```

Twelve rows, one per horizon month. `mean` is the point forecast, `0.1`–`0.9` the predictive
quantiles, `actual` the realised index value. All on 2021=100.

### 5.3 Ensemble weights — from row 49

```
model | family | variant | release_date | weight
```

Every fitted model with its weight in the final ensemble. Weights sum to 1; models that received
none appear with weight 0 — **that is a result, not a gap.**

`family` is `pretrained-foundation` or `trained-from-scratch`. For pretrained models
`release_date` gives when those weights were published, which supports a contamination check:
nothing released after a model's publication can have been in its pretraining corpus.

### 5.4 Post-hoc metrics — from row 69

```
em_code | metric_name | representation | value
```

**All 18 metrics are computed on every run, regardless of which one drove the fitting.** This is
what makes the block analysable: you can score a model fitted on DTW using MASE, and build the
full 17 × 18 objective-versus-yardstick matrix.

Each metric appears three times, once per `representation`:

| Representation | Meaning |
|---|---|
| `level` | the index itself |
| `period_on_period` | month-on-month change |
| `year_on_year` | 12-month inflation rate |

**Which representation to use matters.** A CPI level almost always rises, so directional and
temporal metrics are close to degenerate on it — in the sample run, TDA scores 1.000 and TDI
0.000 at `level`, which says nothing about the model. For EM12–EM18, read
`year_on_year` or `period_on_period`. For point-accuracy metrics the `level` figures are
meaningful.

### 5.5 Release-date labels — from row 123

Per pretrained variant, whether this origin's horizon is `fully_pre`, `straddling` or
`fully_post` relative to that model's public release. For the contamination analysis, compare
pretrained against from-scratch models *within* each period and then compare those gaps —
a raw before/after comparison is confounded with economic regime.

---

## 6. Known issues in the current output

Three things to be aware of before analysing. None invalidates the run; all affect what you can
read from which column.

1. **WQL, SQL and MQL (EM9–EM11) have values only at `level`.** The `period_on_period` and
   `year_on_year` rows are blank, because quantile losses need quantiles in the transformed
   space and only level-space quantiles are produced. Use the `level` figures for these three.
2. **EM12–EM18 show `metric_name` as the code** (`EM12` rather than `DTW`). Cosmetic; the
   mapping is in §2 and on the `METRICS` sheet of `Main_Experiment_Plan.xlsx`.
3. **Directional and temporal metrics are degenerate at `level`**, as described in §5.4. Expected
   behaviour, not a bug — but do not report those numbers.

---

## 7. What is complete

The run proceeds **variable by variable**, so completion is uneven by design.

As of this document: **188 of 306 runs.** HCPI is **complete** — all 17 metrics × 6 origins.
FCPI is partial. CCPI has not started.

**The HCPI slice is self-contained and analysable now.** A full 17-objective comparison for one
variable is a legitimate unit of analysis; the other two extend it, they do not correct it.

To check current coverage, count the sheets or the run-config files:

```
ls Results/RunConfigs/Blk11_MetricSearch/ | wc -l
```

and join the `exp_id`s against `Code/experiments.csv` to see which variable, metric and origin
each corresponds to.

---

## 8. What must NOT be concluded yet

- **No winning metric has been chosen.** The selection rule is an open decision in the plan
  (activity P1-08) and must be agreed *before* the results are examined, or the choice looks
  fitted to the answer.
- **Do not select on a single yardstick.** Judging 17 fitting objectives by one metric will
  crown whichever objective matches that yardstick, almost by construction. The defensible
  approach uses the full 17 × 18 matrix and asks which objective is *robust* across yardsticks,
  which objectives are redundant with each other, and which best anticipates the events a
  central bank acts on.
- **Six origins is a thin basis.** If the top few metrics sit within the spread across origins,
  the honest finding is "these metrics are equivalent here" — which is itself a useful result.
- **Nothing here speaks to crisis conditions.** See §3.

---

## 9. Reproducing a single run

Every result carries enough provenance to be rebuilt: `Code/experiments.csv` gives the design row,
the sheet header gives the resolved window and settings, and the matching
`Results/RunConfigs/Blk11_MetricSearch/<exp_id>.json` records the AutoGluon version, seed, GPU and
the exact model pool fitted. Input data is `Data/final_data.csv`, whose provenance and validation
are documented in `Data/methodology_data_collection.md`.
