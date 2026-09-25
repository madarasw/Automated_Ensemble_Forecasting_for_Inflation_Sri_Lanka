# Reproducing the results

This file explains how to rebuild the paper's results from this repository. The
tagged release `v1.0-paper` is the state of code and results that matches the
submitted manuscript.

**Deep models are not bit-reproducible on a GPU.** The Chronos family and the other
PyTorch models use non-deterministic CUDA kernels, so a re-run with the same seed,
data and code will produce slightly different forecasts, ensemble weights and
scores. The numbers committed under `Results/` are the ones reported in the
paper. A re-run should come close to them, but it will not match them exactly.

## Metric codes

The paper numbers the seventeen fitting objectives EM1–EM17. The code, configs,
`Code/experiments.csv` and every result workbook number the same metrics EM2–EM18.
Paper EM*k* = artifact EM(*k*+1). The full mapping is in
[`EM_CODE_MAP.csv`](EM_CODE_MAP.csv).

## Environment

| Item | Value |
|---|---|
| Python | 3.10.11 |
| Forecasting framework | AutoGluon-TimeSeries 1.6.3 |
| PyTorch | 2.13.0 + CUDA 13.0 (`torch==2.13.0+cu130`) |
| Chronos | chronos-forecasting 2.3.2 |
| Full pinned list | [`requirements.txt`](requirements.txt), from `pip freeze` of the environment that produced the results |

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install torch==2.13.0+cu130 --index-url https://download.pytorch.org/whl/cu130
pip install -r requirements.txt
pytest -m "not slow"          # metric hand-worked checks, post-hoc scoring, leakage tests
```

Chronos weights are downloaded from the Hugging Face Hub on first use.

## Hardware used for the committed results

- One NVIDIA GeForce RTX 5050 Laptop GPU (8 GB VRAM), driver 592.15, CUDA runtime 13.0.
- The 405 runs took 30.9 GPU-hours in total: a mean of 274 s per run under a 900 s
  time limit.
- Each run's hardware, runtime and library version are recorded in
  `Results/RunConfigs/<block>/<exp_id>.json`.

## Fixed settings (every experiment)

| Setting | Value |
|---|---|
| Frequency | Monthly |
| Rolling training window | 124 months = 100 fit + 24 validation |
| Validation | 2 windows of 12 months (`num_val_windows=2`) |
| Forecast horizon | 12 months |
| Random seed | 123 |
| `refit_full` | disabled |
| Quantile levels | 0.1, 0.2, …, 0.9 |
| Time limit | 900 s per run |
| Model pool | Fixed 14-model pool plus Chronos (small), Chronos-Bolt (small) and Chronos-2 |

These values come from the per-block configs in `Code/common/config_*.yaml` and are
also written into each run's JSON under `Results/RunConfigs/`.

## Data

`Data/final_data.csv` is the assembled monthly series that every run reads. It is
built from the Department of Census and Statistics releases (`Data/dcs_*.csv`, parsed
from the PDFs in `Data/` and `Data/pdfs/` by `Code/common/parse_dcs_ncpi.py`) by:

```powershell
python Code/common/build_final_data.py
```

`Data/final_data_notes.md`, `Data/sources.md` and `Data/methodology_data_collection.md`
document the sources, the chain-linking of the 2013 and 2021 bases, and the checks
applied. `Data/fetch_data.py` retrieves the IMF, World Bank and FRED comparison
series. Those series are used only for source comparison. They are not forecast
targets. The FRED fetch needs a free API key in the `FRED_API_KEY` environment
variable.

## The experiment register

`Code/experiments.csv` lists every planned experiment (1,275 rows). The paper uses
405 of them:

| Paper block | `block` column | Row filter | Runner | Runs |
|---|---|---|---|---|
| A: objective search | `1.1` | `block == "1.1"` | `Code/Blk11_MetricSearch/Blk11_MetricSearch.py` | 306 |
| B: origin extension | `2.1` | `block == "2.1"` **and** `exp_id` starts with `B21-` | `Code/Blk2_Selected_PreOn/Blk2_Selected_PreOn.py` | 99 |

Take care with Block B. Filtering on `block == "2.1"` alone also returns 36 `BL-M-*`
baseline rows, which belong to `Code/Blk5_Baselines/`. The Block B runner applies
both conditions and checks for exactly 99 rows before it fits anything.

Each row supplies the index, the fitting metric (`eval_metric`, artifact numbering),
the training window (`train_data_start` to `train_data_end`) and the horizon.

## Re-running one experiment

Take the `exp_id` from a row of `Code/experiments.csv` and pass it to that block's
runner. Use `--force` to replace a result that is already committed. Otherwise the
runner resumes and skips any `exp_id` that already has a result sheet.

```powershell
# Block A, e.g. HCPI fitted on artifact EM11 (paper EM10, MQL)
python Code/Blk11_MetricSearch/Blk11_MetricSearch.py --exp-id B11-M-055 --force

# Block B
python Code/Blk2_Selected_PreOn/Blk2_Selected_PreOn.py --exp-id B21-M-001 --force
```

The run writes one sheet named after the `exp_id` to the block's workbook
(`Results/Results_Blk11_MetricSearch.xlsx` or `Results/Results_Blk2_Selected_PreOn.xlsx`)
and a provenance JSON to `Results/RunConfigs/<block>/<exp_id>.json`.
`--time-limit` and `--random-seed` override the config values.

## Re-running the whole suite

```powershell
python Code/Blk11_MetricSearch/Blk11_MetricSearch.py --force      # 306 runs
python Code/Blk2_Selected_PreOn/Blk2_Selected_PreOn.py --force    # 99 runs
```

Expect about 31 GPU-hours on hardware like that listed above. Leave out `--force`
if you want an interrupted run to resume where it stopped. Both runners take
`--index HCPI|FCPI|CCPI`, so the work can be split across machines.

## From run workbooks to paper tables

See [`TABLE_MAP.md`](TABLE_MAP.md). It maps each table in the paper to its
derived file under `Results/Analysis/` and shows where the builder script is
missing.
