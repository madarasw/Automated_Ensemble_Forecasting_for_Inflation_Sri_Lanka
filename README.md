# Interpretable Automated Ensemble Forecasting for Inflation
### A Comprehensive Benchmarking Framework for Sri Lanka

Research paper for submission to a conference organised by the **Central Bank of Sri Lanka**.
Track: *Digitalisation, AI, and Data in Macroeconomic Analysis*.

---

## Read this first

If you have just cloned this repository and are not sure what to do, this file is the complete
briefing. It explains what the research is, what every folder is for, what order the experiments
run in, and which decisions are still open. You do not need to read anything else to get started.

**Start with `Research.xlsx`.** It is the top-level project plan — four phases, 37 activities,
with a tab per phase. It tells you what to do and in what order. `Main_Experiment_Plan.xlsx` holds
the 1,562 individual forecasting runs and comes into play in Phase 3.

**The single most important thing to understand:** the experiments do **not** run in tab order.
We run **Tabs 5–21 first** to find out which evaluation metric is best, and only then run Tabs 1–4.
See [Execution order](#execution-order) below.

---

## What the research is about

Inflation forecasting matters for monetary policy, and Sri Lanka is a hard case — structural
breaks, exchange-rate volatility, commodity shocks, and the 2022 economic crisis all sit inside
the evaluation period.

This study benchmarks a **modern automated ensemble forecasting framework** on Sri Lankan
inflation. Rather than picking one model, the framework evaluates many forecasting models —
classical statistical methods, gradient boosting, and transformer-based deep learning foundation
models — and combines them into a weighted ensemble.

The contribution is **interpretability**: instead of treating the ensemble as a black box, we
study *how the ensemble weights are allocated* and *how that allocation changes* across inflation
indices, data frequencies, evaluation metrics, and economic regimes.

### The four research questions

1. **How effectively** can modern automated ensemble forecasting systems predict Sri Lankan
   inflation across different forecast horizons?
2. **How do ensemble weights** assigned to different forecasting models vary across inflation
   components, data frequencies, different evaluation metrics, and economic regimes?
3. **Which evaluation metrics** provide the most meaningful assessment of forecasting quality
   within the Sri Lankan macroeconomic context?
4. How does the inclusion of macroeconomic explanatory variables and varying historical training
   lengths influence forecasting accuracy and the relative contribution of deep learning
   foundation models?

> **Question 4 is deliberately deferred.** It is not covered by the current experiment plan and
> will be added as additional tabs later. Do not plan work around it yet.

### The four inflation indices

| Code | Index |
|---|---|
| `HCPI` | Headline Consumer Price Index |
| `FCPI` | Food Consumer Price Index |
| `CCPI` | Core Consumer Price Index |
| `ECPI` | Energy Consumer Price Index |

---

## Repository structure

```
Automated_Ensemble_Forecasting_for_Inflation_Sri_Lanka/
├── README.md                    <- this file
├── Research.xlsx                <- TOP-LEVEL PLAN. 4 phases, 37 activities. Start here.
├── Main_Experiment_Plan.xlsx    <- THE EXPERIMENTS. 1,562 runs. Used in Phase 3.
├── Abstract.pdf                 <- the submitted abstract
│
├── Code/
│   ├── experiments.csv          <- machine-readable mirror of the plan (1,562 rows)
│   ├── common/
│   │   ├── config_Tab01_HCPI_EM1.yaml    <- settings for that tab
│   │   └── ... one config per tab (21) ...
│   ├── Tab01_HCPI_EM1/
│   │   └── Tab01_HCPI_EM1.ipynb <- ONE notebook, loops all of that tab's experiments
│   ├── Tab05_HCPI_EM2/
│   │   ... one folder per tab in the plan ...
│   └── Tab21_HCPI_EM18/
│
├── Data/                        <- all input time series as CSV
│                                   e.g. HCPI.csv, FCPI.csv, Oil_price.csv
│
└── Results/                     <- one Excel file per tab, one sheet per experiment
                                    e.g. Results_Tab05_HCPI_EM2.xlsx
```

**One notebook per tab, not one per experiment.** Within a tab, the only thing that changes
between experiments is the forecast origin — the index, frequency, evaluation metric and every
setting stay the same. So each tab has a single notebook that reads `experiments.csv`, filters to
its own tab, and loops through that tab's rows. 21 notebooks, not 1,562.

Each `Code/Tab*/` folder currently contains only a `.gitkeep` file. That is a placeholder — Git
cannot store an empty folder, so the file exists purely to preserve the structure. Ignore it and
delete it once the real notebook lands in that folder.

---

## Research.xlsx — the top-level plan

This is the project tracker. Open it first.

| Sheet | What it is |
|---|---|
| `Overview` | How the two workbooks fit together |
| `Phase1_Get_Ready` | Data, and the decisions everything else depends on — 10 activities |
| `Phase2_Build_Pilot` | Build the machinery on one experiment, then one tab — 10 activities |
| `Phase3_Run` | Stage 1 then Stage 3, executed through the experiment plan — 7 activities |
| `Phase4_Analyse_Write` | Answer the three research questions, write the paper — 10 activities |

One row is one activity. The columns are `Activity ID`, `Description`, `What to finalize`,
`Results`, `Who did it?`, `Done?`.

**`What to finalize` is the column that matters.** It states the decision or output that must be
locked before moving on — the thing that stops an activity sitting at "mostly done" for three
weeks. Activity P1-05 is not finished when the target transformation has been *discussed*; it is
finished when one choice is written down and applied everywhere.

**Seven rows are shaded orange.** These are gates, where getting it wrong invalidates later work
rather than merely delaying it:

- `P1-05` – `P1-08` — the target transformation, the AutoGluon controls, copying them into all 21
  configs, and the metric selection rule. Settings frozen here cannot change once runs begin
- `P2-08`, `P2-09` — the Tab 5 pilot and the compute projection. The go/no-go before committing
  to 1,562 runs
- `P3-03` — choosing the evaluation metric, which must follow the rule agreed in `P1-08`

### How the two workbooks relate

`Research.xlsx` tracks the **project**. `Main_Experiment_Plan.xlsx` tracks the **runs**.

Phase 3 has only 7 activity rows because at that level "run tabs 5–21" is a single activity — the
1,173 runs inside it are tracked row by row in the experiment plan. The two meet at activity
`P3-02`: as each run completes, fill in `status`, `runtime_sec`, `hardware` and `run_date` in the
plan. That is also where the execution-time evidence the abstract promises comes from.

---

## Main_Experiment_Plan.xlsx — how to read it

This workbook is the source of truth. Every experiment we run comes from a row in it.

| Sheet | What it is |
|---|---|
| `README` | Summary of the plan, inside the workbook |
| `MASTER` | **All 1,562 experiments in one filterable list.** Start here |
| `Tab01` … `Tab04` | The four indices under the *selected* metric — Stage 3 |
| `Tab05` … `Tab21` | HCPI monthly under each candidate metric — **Stage 1, run first** |
| `METRICS` | The 18 metric codes, what each is, and implementation warnings |
| `REGIMES` | The six economic regimes used to group results |
| `CONTROLS` | Settings that must be identical across every run — **fill before starting** |
| `COVERAGE` | Cross-check of the research questions against the planned experiments |

### Colour code in the workbook

- **Yellow cells** — you fill these in as work progresses (`status`, `runtime_sec`, `hardware`,
  `run_date`, `notes`)
- **Green cells** — `train_data_end`, already calculated. Never work this out by hand
- **Orange cells** — something is undecided or needs attention

---

## Execution order

This is the part that is easy to get wrong.

### Stage 1 — find the best evaluation metric (run this first)

**Tabs 5–21 · 1,173 experiments · HCPI, monthly only**

Each of these 17 tabs runs the *same* forecasts with a *different evaluation metric* as the
ensemble's fitting objective. Changing the objective changes which models the ensemble picks and
how it weights them — that is exactly what we are measuring.

The 17 candidate metrics cover everything the abstract promises:

| Codes | Family | Metrics |
|---|---|---|
| EM2–EM8 | Point accuracy (7) | MAE, RMSE, MAPE, sMAPE, MASE, RMSSE, WAPE |
| EM9–EM11 | Proper scoring rules | WQL, SQL, MQL |
| EM12–EM15 | Temporal similarity | DTW, Soft-DTW, Wasserstein, TDI |
| EM16–EM18 | Directional | TDA, DA, TPA |

Execution time is recorded on *every* run in the `runtime_sec` column rather than getting its own
tab — it cannot be used as a fitting objective.

### Stage 2 — choose the winner

Decide which metric performed best. Record it as **EM1** on the `METRICS` sheet and fill in the
`eval_metric` / `metric_name` columns of Tabs 1–4.

> **The decision rule must be agreed BEFORE Stage 1 finishes.** "Most meaningful" is not something
> the numbers announce by themselves, and choosing after seeing the results looks like the answer
> was fitted to the data. See [Open decisions](#open-decisions).

### Stage 3 — the full sweep

**Tabs 1–4 · 389 experiments · all four indices, all three frequencies**

Re-run with the winning metric, now across HCPI, FCPI, CCPI and ECPI at monthly, quarterly and
annual frequency.

### Totals

| Stage | Tabs | Experiments |
|---|---|---|
| 1 — metric search | 5–21 | 1,173 |
| 3 — full sweep | 1–4 | 389 |
| | | **1,562** |

---

## How a forecast is set up

### The rolling-origin rule

**Training data ends the period immediately before the horizon starts.** No exceptions.

| Horizon | Train on data up to |
|---|---|
| Jan 2020 – Dec 2020 (12 months) | Dec 2019 |
| Q1 2020 – Q4 2020 (4 quarters) | Q4 2019 |
| 2020 (1 year) | 2019 |

This is already calculated for every experiment in the green `train_data_end` column. Use that
column — do not recompute it.

Training always starts at the beginning of the series (an expanding window). Varying the training
length is Research Question 4 and is out of scope for now.

### The origins

| Frequency | Horizon length | First horizon | Last horizon | Count |
|---|---|---|---|---|
| Monthly | 12 months | Jan 2020 – Dec 2020 | Sep 2025 – Aug 2026 | 69 |
| Quarterly | 4 quarters | Q1 2020 – Q4 2020 | Q3 2025 – Q2 2026 | 23 |
| Annual (HCPI) | 1 year | 2020 | 2025 | 6 |
| Annual (FCPI/CCPI/ECPI) | 1 year | 2021 | 2025 | 5 |

Each horizon rolls forward one period at a time.

### Economic regimes

Research Question 2 asks how weights vary across economic regimes. **No extra experiments are
needed** — the 69 monthly origins already span every regime. Each experiment carries a
`regime_of_horizon_start` label, and the weight analysis groups by it.

| Regime | Horizon starts in | Character |
|---|---|---|
| R1 | 2020 | COVID-19 shock |
| R2 | 2021 | Pre-crisis build-up |
| R3 | 2022 | Crisis and hyperinflation (YoY peaks near 70%) |
| R4 | 2023 | Sharp disinflation |
| R5 | 2024 | Deflation and stabilisation |
| R6 | 2025 | Post-stabilisation |

---

## Naming conventions

### Experiment ID — `T05-M-001`

- `T05` — tab number
- `M` — frequency (`M` monthly, `Q` quarterly, `A` annual)
- `001` — sequence within that tab and frequency

**Experiment IDs are permanent. Never renumber them.** They tie together the plan row, the
notebook and the results sheet. If an experiment is added later, give it the next free number.

### Notebooks

```
Code/<tab folder>/<tab name>.ipynb
```
Example: `Code/Tab05_HCPI_EM2/Tab05_HCPI_EM2.ipynb` — one notebook covering all 69 experiments in
that tab.

The experiment ID identifies a **row in `experiments.csv`**, not a file. The `notebook` and
`tab_config` columns of the plan give the exact paths for every experiment.

### Results

One Excel file per tab, one sheet per experiment:

```
Results/Results_<tab name>.xlsx     sheet name = experiment ID
```
Example: `Results/Results_Tab05_HCPI_EM2.xlsx`, sheet `T05-M-001`

The exact destination for every experiment is in the `result_workbook` and `result_tab` columns.

### What each run records

| Tabs | Records |
|---|---|
| 1–4 | Point forecasts + ensemble weight distribution |
| 5–21 | Point forecasts + quantile forecasts + ensemble weight distribution |

Plus, on every run: execution time and the hardware it ran on.

---

## How a notebook works

Each tab notebook does the same five things:

1. Read `Code/common/config_<tab name>.yaml` — the settings constant across that tab
2. Read `Code/experiments.csv` and filter to `tab_name == "<tab name>"`
3. For each row: train on data from the series start through `train_data_end`, forecast the
   horizon, record what the tab is specified to record
4. Write results to `Results/Results_<tab name>.xlsx`, one sheet per `exp_id`, plus a small
   `run_config.json` capturing exactly what was used — framework version, seed, hardware,
   resolved training window
5. **Skip any experiment that already has results.** A Colab session will disconnect somewhere in
   a 69-experiment loop; without this, a drop at experiment 60 costs all 60

### The tab config files

`Code/common/config_<tab name>.yaml` holds everything constant for that tab: the index, the
evaluation metric, what to record, and the shared `controls:` block.

These are plain text, so Git can diff and merge them — unlike the `.xlsx`. That is why the
notebooks read the CSV and the YAML rather than the workbook directly.

**The `controls:` block must be identical in all 21 files.** Fill it in once and copy it
everywhere. See the next section for why this matters.

### After editing the plan

`experiments.csv` and the YAML files are **generated from** `Main_Experiment_Plan.xlsx`. If you
change the plan, regenerate them, or the notebooks will keep running the old version. Ask Claude
to regenerate them from the workbook.

---

## Before the first experiment runs

Open the **`CONTROLS`** sheet and fill it in. It lists the settings that must be **identical
across all 1,562 runs** — framework version, model pool, time limit per fit, quantile levels,
target transformation, random seed, and so on.

This is not housekeeping. The entire Stage 1 comparison rests on the evaluation metric being the
**only** thing that differs between Tabs 5 and 21. If one tab happens to run with a longer time
budget than another, the difference in ensemble weights gets blamed on the metric when it was
really the budget — and the paper's central finding would be wrong.

Agree these values once, write them down, and do not change them mid-study. If one genuinely has
to change, every completed run has to be repeated.

---

## Open decisions

These are not yet settled. They are flagged in the workbook too.

**1. The metric selection rule (Stage 2).** Agree it before Stage 1 finishes. Three criteria that
work well together:
- *Redundancy* — rank-correlate what the 17 metrics say about model rankings, and drop the ones
  that say the same thing as another
- *Stability* — does a metric's ranking hold across regimes R1–R6? One that flips is useless for
  choosing a model
- *Policy relevance* — which metric's chosen model best anticipates the events the Central Bank
  actually acts on (inflation target-band breach, direction change, turning point)?

That last one is what makes the answer specific to Sri Lanka. Without it, the same 17 runs on any
country's CPI would answer Question 3 identically.

**2. Target transformation.** Do we forecast the index level, the year-on-year percentage change,
or the log difference? This is not specified anywhere yet, and it changes model rankings more than
most of the metrics do. Decide once and apply everywhere.

**3. No baseline yet.** Question 1 asks how *effectively* the ensemble forecasts. Nothing in the
current 21 tabs answers "effective compared to what?" A seasonal-naive and an ARIMA reference over
the same origins would fix it cheaply — statistical models fit in seconds. Worth adding one tab.

**4. Three metrics are awkward as fitting objectives.** See the `Implementation caution` column on
the `METRICS` sheet:
- **TPA (EM18)** can be *undefined* — a 12-month window often contains no turning point at all,
  and then the metric cannot rank models. Needs a fallback rule
- **TDA and DA (EM16, EM17)** are coarse: on a 12-step horizon each takes at most 13 distinct
  values, so models tie constantly and weights become unstable
- **MAPE (EM4)** breaks where year-on-year inflation crosses zero, which Sri Lanka does in 2024

Also, EM12–EM15 are not built into the forecasting framework and need custom scoring code written
and tested first. **Wasserstein (EM14)** additionally needs a definition decision — computed on
the value distribution alone it is order-independent, so shuffling the forecast in time would not
change it.

**5. Quantiles in Tabs 1–4.** Those tabs are specified to record point forecasts only. If the
winning EM1 turns out to be WQL, SQL or MQL, they must record quantiles too — otherwise the
chosen metric cannot be computed on them.

**6. Naming note for the CBSL audience.** This project uses `CCPI` for *Core* CPI, following the
abstract. In Sri Lanka, CCPI conventionally means the **Colombo** Consumer Price Index. Worth
adding one clarifying sentence to the paper so reviewers are not misled.

**7. The last monthly horizon cannot be scored yet.** `T*-M-069` runs Sep 2025 – Aug 2026 and
needs actuals through Aug 2026. Run it, but hold the evaluation until that figure is published.
Those rows are flagged in the `notes` column. Quarterly and annual are unaffected.

---

## Working together on this repository

We are two people sharing one repository. A few habits avoid trouble.

**Always pull before you start work.**
```bash
git pull
```

**Commit and push when you finish something.**
```bash
git add .
git commit -m "Add notebook T05-M-001"
git push
```

**Talk to each other before both editing `Main_Experiment_Plan.xlsx`.** Excel files cannot be
merged by Git. If you both edit it at the same time, one person's changes are lost. Agree who is
editing the plan before touching it.

**Never renumber an experiment ID**, even if the numbering looks untidy.

**Do not commit large files without checking.** GitHub rejects anything over 100 MB.

---

## Quick reference

| Question | Answer |
|---|---|
| Where do I start? | `Research.xlsx`, Phase 1 tab |
| What is the next action right now? | `P1-01` — get the data. `Data/` is still empty |
| Where are the 1,562 experiments? | `Main_Experiment_Plan.xlsx`, `MASTER` sheet |
| Which experiments first? | Tabs 5–21 (Stage 1) |
| What is EM1? | Not decided yet — it is whichever metric wins Stage 1 |
| Where do notebooks go? | `Code/<tab folder>/<tab name>.ipynb` — one per tab |
| What is an experiment ID then? | A row in `Code/experiments.csv`, not a file |
| Where do results go? | `Results/Results_<tab name>.xlsx`, one sheet per experiment |
| How much data does a run get? | See the green `train_data_end` column |
| Is Question 4 in scope? | No — deferred to later |
| What must be done before running? | Fill in the `CONTROLS` sheet |
