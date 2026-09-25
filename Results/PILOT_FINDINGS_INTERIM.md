# Tab 5 pilot — interim findings before committing to the full 69-run pilot

**Status:** 11 of 69 `Tab05_HCPI_EM2` experiments run for real, on GPU — one per economic
regime plus extras, per your instruction to gather more samples before deciding. This is
the P2-09 checkpoint working as designed: better to find this at run 11 than run 69.

## What's confirmed working

P2-01 through P2-07 are fully validated against the real pipeline, not just unit tests:
real GPU fit (RTX 5050 Laptop, 8.5GB VRAM, CUDA 13.0 runtime — confirmed with an actual
matmul, not just `torch.cuda.is_available()`, after discovering that check alone is not
reliable: an earlier cu126 torch build reported CUDA "available" while actually having no
compiled kernels for this GPU's compute capability; `gpu.require_cuda()` now runs a real
op and would have caught this itself), point + quantile forecasts, per-model ensemble
weights tagged pretrained-vs-scratch with release dates, all 18 post-hoc metrics on all 3
representations, resume/skip logic, and `run_config.json` provenance. All 20 real tabs'
runner scripts + Tab 22's baseline runner generated and working; Excel plan surgery
(task 9) and Tab 22 (task 10) complete, verified, and idempotent.

## Finding 1: 600s time_limit is not enough — 900s reliably is

| exp_id | time_limit | fit+predict time | models skipped |
|---|---|---|---|
| T05-M-001 | 600s | 576.1s | **Chronos[small], Chronos[bolt_small], AutoCES** |
| all 10 others | 900s | 377.7s – 583.9s | **none — full 16-model pool fit every time** |

At 600s, two of three Chronos variants never got a chance to fit — not "fit and score
poorly," genuinely absent. That breaks CONTROLS's "same pool for every run" promise: a
difference later attributed to the evaluation metric could really be which models
survived the clock. 900s fit the complete pool in all 10 follow-up runs, with margin.
**Recommend freezing `time_limit = 900s`.**

## Finding 2 (revised from the first 3-sample snapshot): the Chronos family is NOT dead weight

The first 3 samples (all early-regime origins) showed every Chronos variant at zero
ensemble weight, which looked like a case for trimming them. Across the full 11 samples
spanning all six regimes, that reverses:

| model | avg weight (of 11) | origins with nonzero weight |
|---|---|---|
| AutoARIMA | 0.250 | 6 / 11 |
| **Chronos2** | **0.155** | **4 / 11** |
| AutoETS | 0.104 | 7 / 11 |
| Theta | 0.085 | 4 / 11 |
| AutoCES | 0.078 | 4 / 11 |
| DeepAR | 0.077 | 2 / 11 |
| **Chronos[bolt_small]** | **0.077** | **3 / 11** |
| Naive | 0.077 | 3 / 11 |
| RecursiveTabular | 0.041 | 2 / 11 |
| **Chronos[small]** | **0.027** | **4 / 11** |
| TemporalFusionTransformer | 0.021 | 2 / 11 |
| DirectTabular | 0.007 | 1 / 11 |
| TiDE | 0.001 | 1 / 11 |
| SeasonalNaive, NPTS, PatchTST | 0.000 | 0 / 11 |

All three Chronos variants pull real, sometimes substantial weight (Chronos2 averages
0.155 across all 11 — higher than most from-scratch models) once later-regime origins are
included. **The n=3 sample was simply too small and happened to catch a run of origins
where Chronos lost out; dropping the pretrained family would have been the wrong call**,
and would have gutted exactly the RQ4/abstract promise the frozen model-pool decision
exists to keep. Only three models (SeasonalNaive, NPTS, PatchTST) scored zero in all 11
runs — a much narrower, better-supported trim candidate than the original list, though
still n=11.

## Finding 3: fit time trends up with training-window length (expanding window)

| regime | origins sampled | fit+predict time |
|---|---|---|
| R1 COVID (2020) | M-002, M-006 | 406.5s, 407.3s |
| R2 pre-crisis (2021) | M-018 | 428.9s |
| R3 crisis (2022) | M-025, M-036 | 433.2s, 377.7s |
| R4 disinflation (2023) | M-042, M-048 | 522.3s, 559.0s |
| R5 deflation (2024) | M-055 | 583.9s |
| R6 post-stabilisation (2025) | M-065, M-069 | 580.9s, 547.8s |

A clear upward trend from ~410s (early, ~72 months of training data) to ~565s (late,
~140 months) — expected for an expanding window, and means a flat average understates
later origins and overstates earlier ones. Mean across all 10 valid (900s-budget) samples:
**484.8s**, reasonably representative since the 11 samples already span the full regime
range that all 69 origins cover.

## The compute budget, updated

At 484.8s average, spanning the same regime range as the full 69:

- **Tab 5 alone (69 runs):** 69 × 484.8s ≈ **9.3 hours**
- **All 17 Stage-1 tabs (Tabs 5-21, 1,173 monthly-HCPI runs, same origins each time):**
  17 × 9.3h ≈ **158 hours ≈ 6.6 days** of continuous GPU time (assumes fitting objective
  doesn't change timing much — plausible, since model *training* dominates over the
  scoring pass, but not yet verified on a second tab)
- **Stage 3 (Tabs 1-3, 294 runs: monthly + quarterly + annual, 3 indices):** monthly
  origins dominate; quarterly/annual are shorter-horizon and likely faster but
  unmeasured. Rough estimate ≈ 1.0–1.5 days.
- **Total for all 1,467 AutoGluon-dependent runs: ≈ 7.5–8 days of continuous GPU time.**
  Tab 22 (294 baseline rows) is already done (4m35s total, negligible).

## What I need from you

This confirms the first estimate rather than changing it: **900s/16-model pool is
correct and defensible, but the total budget is still ~8 days of continuous compute.**
Trimming the 3 always-zero models (SeasonalNaive, NPTS, PatchTST) would save maybe
15-20% of per-run time, not resolve the order-of-magnitude issue. The real levers are
still: (a) accept the multi-day unattended run, (b) cut `num_val_windows` from 3 toward
1, or (c) accept a shorter `time_limit` with a documented, deliberate trim of the model
pool (not just the 3 zero-weight ones — a bigger cut than the data currently justifies).
I have not started the remaining 58 Tab 5 runs, or any other tab. Your call.
