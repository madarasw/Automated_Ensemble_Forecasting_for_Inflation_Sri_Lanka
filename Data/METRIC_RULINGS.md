# Metric implementation rulings — decision memo (P1-09, task 6)

**These are proposals, not decisions.** Each of the four open rulings from the METRICS
sheet / `INDEX_SET_CHANGE.md` is implemented with a documented default so Stage 1 can
run, but every default below needs your ratification before Stage 1's results are
treated as final. If you want a different rule, the change is confined to
`Code/common/metrics/` and does not touch the experiment plan.

Evidence in (a)–(c) is computed directly from `Data/final_data.csv` — the real published
HCPI/FCPI/CCPI series — via `Code/common/metric_rulings_diagnostics.py`, not simulated.
Re-run that script any time the data changes; it takes seconds and needs no GPU.

---

## (a) MAPE at the zero-crossing

**On the level (the actual fitting target for EM4/Tab 7): moot.** MAPE is computed on
the index level, which is strictly positive throughout the series (an index never
crosses zero), so EM4 as the *fitting objective* never divides by a near-zero number.

**On the YoY post-hoc column: a real, large problem.** Every experiment's post-hoc table
(`Code/common/metrics/posthoc.py`) also reports MAPE computed on the year-on-year
representation, and Sri Lankan YoY inflation genuinely crosses zero in 2024. Measured
directly from the data: of the 69 monthly rolling-origin windows, the actual YoY path
crosses zero *within the 12-month horizon* in:

| Index | Origins with a zero-crossing in horizon | Share |
|---|---|---|
| HCPI | 20 / 69 | 29% |
| FCPI | 32 / 69 | 46% |
| CCPI | 23 / 69 | 33% |

All three clusters fall in the same window — Oct 2023 through mid-2025, i.e. every
origin whose horizon overlaps the 2024 deflation. FCPI is worst (food deflation was
sharper). At those origins, MAPE-on-YoY for any actual value near zero blows up toward
infinity for a small forecast error, or is undefined if the actual is exactly zero.

**Proposal:** report MAPE-on-YoY for these origins as `NaN` with an explicit flag
(already how `posthoc.py` behaves when a native scorer returns `inf`/`nan` — nothing is
silently clipped or substituted), and exclude EM4-on-YoY from any post-hoc ranking or
average computed across origins unless the average is explicitly restricted to
non-crossing origins. Do not use MAPE-on-YoY as a candidate for EM1 selection at Stage
2. WAPE/SMAPE are already in the point-metric family and don't share this failure mode —
prefer those for any YoY point-accuracy comparison that needs all 69 origins.

---

## (b) TPA when a window has no turning point

Measured directly (Bry–Boschan-style dating rule, `Code/common/metrics/directional.py`,
±1-period tolerance) across all 69 monthly origins per index, using the *actual*
[origin, h1..h12] YoY sequence — 13 points per window:

| Index | Origins with zero actual turning points | Which |
|---|---|---|
| HCPI | 1 / 69 | 2021-10 |
| FCPI | 1 / 69 | 2021-10 |
| CCPI | 2 / 69 | 2021-10, 2022-10 |

Rare (1–3%), and clustered at the same calm pre-crisis window (late 2021, just before
the 2022 shock) — exactly where a 12-month YoY path is smooth enough to have no local
extremum under the simplified (no minimum-phase-length) dating rule.

**Proposal:** the implemented default (`turning_point_accuracy()`) already returns a
neutral 0.5 ("no information", not a crash) for these windows rather than raising, so
Tab 21's ensemble fitting never breaks. Given how rare this is, **skip-the-origin is
also viable and arguably cleaner** for Stage 2 comparison purposes (excluding 1–3 origins
out of 69 barely changes statistical power). Recommend: keep the 0.5 fallback for the
*fitting* objective (so Tab 21 always has 69 usable origins to select ensemble weights
from), but exclude these specific origins from any *cross-metric* comparison table in
Stage 2, flagged explicitly rather than silently averaged in.

---

## (c) TDA and DA tie-breaking

Implemented default: a sign comparison counts as a match only when both signs are
*exactly* equal (flat-vs-flat matches; flat-vs-nonzero does not).

Measured directly: across all 69 origins × 12 horizon steps = 828 step-to-step YoY
changes per index, the count of **exactly flat** actual moves is **0 for all three
indices**. Real published inflation data, at one-decimal precision, essentially never
repeats a YoY rate to the point of an exact zero step change.

**Consequence: the tie-break rule almost never actually fires against real actuals.**
The coarseness the METRICS sheet warns about (13 distinct values on a 12-step horizon)
is real and comes from the *count of correct calls* being a small integer, not from
literal sign ties — so a different tie-break rule would not materially change DA/TDA's
behavior on this data. **Proposal: keep the exact-equality tie-break as documented; it
is not a live risk here**, but forecasts (unlike actuals) can and do land on exact
integer/rounded values, so the rule still needs to be stated for the *forecast* side of
the comparison — which it is, symmetrically, in `directional_accuracy()`/
`trend_direction_accuracy()`.

---

## (d) Wasserstein: 1-D value distribution vs 2-D (time, value) cloud

Demonstrated in `Code/common/tests/test_metrics_handworked.py::
test_wasserstein_permutation_invariance_1d_vs_2d` (passing test, not a simulation
described only in prose): for `actual=[0,10]` and two forecasts with the *identical*
value multiset `{0,10}` — one matching actual's order, one reversed —

| Comparison | 1-D Wasserstein | 2-D (time,value) Wasserstein |
|---|---|---|
| actual vs matched-order forecast | 0.0 | 0.0 |
| actual vs time-reversed forecast | **0.0** (unchanged) | **1.0** |

The 1-D form cannot distinguish a forecast that gets the right values in the wrong order
from one that gets them in the right order — for a metric meant to evaluate *forecasts*,
where getting the timing right is the entire point, that is disqualifying.

**Proposal: use the 2-D (time, value) formulation** (`wasserstein_2d_time_value()`,
exact Hungarian-algorithm assignment — no approximation needed at n=12), already the
implemented default (`WassersteinScorer.USE_2D = True`). Caveat carried into the
implementation's docstring rather than hidden: time (a 0..11 step count) and value
(percentage points, post-YoY-transform) are compared as raw numbers on the same
Euclidean scale without renormalisation — a modelling choice. If you want the two axes
rescaled onto a common range before computing distance, say so; it's a one-line change
in `temporal.py`.

---

## Summary of defaults awaiting ratification

| # | Ruling | Implemented default | Confidence this is right |
|---|---|---|---|
| a | MAPE zero-crossing | Moot on level; NaN + excluded from Stage-2 ranking on YoY | High — MAPE-on-YoY is unsalvageable at 29-46% affected origins |
| b | TPA undefined | 0.5 fallback for fitting; excluded from Stage-2 comparison tables | Medium — skip-the-origin is an equally defensible alternative |
| c | DA/TDA ties | Exact-sign-equality match | High — essentially never fires on real actuals (0/828) |
| d | Wasserstein dimensionality | 2-D (time, value), unscaled axes | Medium-high — 1-D is clearly wrong for a forecast metric; the axis-scaling choice is more of a judgement call |
