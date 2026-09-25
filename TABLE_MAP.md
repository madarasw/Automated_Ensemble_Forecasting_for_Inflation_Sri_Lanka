# Paper tables → result files

This map covers every numbered table in `Paper/CBSL_research/main.tex`. The paper
contains **15 tables and no figures**. Metric codes in the result files use artifact
numbering (paper EM*k* = artifact EM(*k*+1)). See `EM_CODE_MAP.csv`.

The rows marked *verified* were checked by recomputing the table's numbers from the
named file.

## Builder scripts

**No script that builds `Results/Analysis/` is in the repository.** Those files
were produced by one-off analysis code that was not kept. The "Script" column
therefore gives the code that produced each file's *inputs*, and lists the builder
as missing. Until that script is added, a reader can recompute each derived table
from the listed file and the run workbooks, but cannot regenerate the derived
files automatically.

## Map

| # | Label | Caption (short) | Result file(s) | Script | Status |
|---|---|---|---|---|---|
| 1 | `tab:origins` | Forecast origins | `Code/experiments.csv` (`origin_no`, `horizon_start`, `train_data_*`) | descriptive: no builder | design table |
| 2 | `tab:models` | Candidate models in the ensemble library | `Code/common/config_Blk11_MetricSearch.yaml`, `Results/RunConfigs/*/*.json` (`model_pool_requested`) | descriptive: no builder | design table |
| 3 | `tab:controls` | Settings held constant | `Code/common/config_Blk11_MetricSearch.yaml`, `config_Blk2_Selected_PreOn.yaml` | descriptive: no builder | design table |
| 4 | `tab:metrics` | The seventeen candidate fitting objectives | `EM_CODE_MAP.csv`; `Code/common/metrics/__init__.py` | descriptive: no builder | verified against registry |
| 5 | `tab:notation` | Notation | none (mathematical notation) | none | not data-derived |
| 6 | `tab:panel` | The four-metric assessment panel | none (design choice) | none | not data-derived |
| 7 | `tab:design` | Executed experiments | `Code/experiments.csv` (`block` 1.1 = 306; 2.1 with `B21-` = 99) | descriptive: no builder | verified (counts) |
| 8 | `tab:panel_top3` | Block A, YoY: three leading objectives per angle/index/window | `Results/Analysis/blockA_YoY_4angle_top5_tables.csv`; `blockA_MASE_by_horizon.xlsx`, `blockA_SQL_by_horizon.xlsx`, `blockA_SoftDTW_cumulative.xlsx`, `blockA_TPA_cumulative.xlsx` | builder **missing**; inputs from `Code/Blk11_MetricSearch/Blk11_MetricSearch.py` → `Results/Results_Blk11_MetricSearch.xlsx` | verified (MASE cells) |
| 9 | `tab:shortlist` | The shortlist carried into the origin extension | `Results/Analysis/panel_4metric_yoy.csv` (`MASE`, `maxw` ≥ 0.90 for Collapse, `Neff`; `block == "A"`); selection narrative in `Results/Blk11_OBJECTIVE_SELECTION.md` | builder **missing**; inputs from Blk11 runner | verified (MASE, Collapse, N_eff) |
| 10 | `tab:stability` | Out-of-sample behaviour of the shortlist (Block A / B / pooled) | `Results/Analysis/panel_4metric_yoy.csv` (`block` A and B) | builder **missing**; inputs from Blk11 and `Code/Blk2_Selected_PreOn/Blk2_Selected_PreOn.py` | verified |
| 11 | `tab:panel17` | Pooled 17 origins: shortlisted objectives per angle and window | **unmatched.** The per-window (1/3/6-month) pooled MASE, SQL, Soft-DTW and TPA scores are not stored in any file under `Results/Analysis/`. The 12-month column matches `panel_4metric_yoy.csv` | builder **missing** | **cannot fully match** |
| 12 | `tab:precision17` | Dispersion of the 12-month MASE across 17 origins | `Results/Analysis/panel_4metric_yoy.csv` (mean, s.d., min, max by `var`,`em`) | builder **missing** | verified |
| 13 | `tab:bench17` | Mean absolute YoY error vs naive benchmarks | `Results/Analysis/blk_pooled17_series.csv` (model), `Results/Analysis/blk_pooled17_naive_benchmarks.csv` (RW, drift, A–O, seasonal naive) | builder **missing** | verified (MAE columns) |
| 14 | `tab:dm17` | Diebold–Mariano vs random walk | inputs: `blk_pooled17_series.csv`, `blk_pooled17_naive_benchmarks.csv`. **No file stores the DM statistics or p-values** | builder **missing** | **inputs only; output unmatched** |
| 15 (App. A) | `tab:appA-point-hcpi` | Block A, HCPI: five leading objectives under MASE, per window | `Results/Analysis/blockA_MASE_by_horizon.xlsx`, sheet `HCPI` | builder **missing** | verified |

## Files in `Results/Analysis/` and `Results/Figures/` not cited by a paper table

These files are committed as supporting analysis. No numbered table in the
manuscript reproduces them directly:

- `blk11_cells.csv`, `blk11_hit*_*.csv`, `blk11_hitrate*.xlsx`, `blk11_hitrates.csv`,
  `blk11_objective_summary.csv`, `blk11_per_variable.csv`, `blk11_yoy*` (Block A
  hit-rate and level-basis diagnostics behind `Results/Blk11_OBJECTIVE_SELECTION.md`)
- `blk_pooled17_DA_*`, `blk_pooled17_hitrate_by_horizon.xlsx`,
  `blk_pooled17_rel2pct_*`, `blk_pooled17_yoy_MAPE*.xlsx` (pooled-17 robustness
  checks, some cited in the text rather than in a table)
- `blockA_*_LEVEL.xlsx`, `blockA_absYoYdiff_by_horizon.xlsx`,
  `blockA_rank_first3months.xlsx`, `blockA_relative1pct_by_horizon.xlsx`
- All five figures in `Results/Figures/` (each PNG has the CSV it was drawn from).
  The manuscript has no `figure` environment and includes none of them.
