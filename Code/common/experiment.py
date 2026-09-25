"""Core experiment runner (P2-01, reused by every tab runner in P2-06/07).

run_single_experiment() is the ONE place that implements "train through train_data_end
inclusive, forecast the horizon" - the P2-01 single-experiment build and every P2-06/07
tab loop both call this, so there's exactly one codepath to leakage-test and get right.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

import autogluon.timeseries as agts
import pandas as pd
import yaml
from autogluon.timeseries import TimeSeriesPredictor

from . import gpu
from .data import (
    FREQ_ALIAS,
    FREQ_TO_PANDAS,
    FREQ_TO_SEASONAL_PERIOD,
    REPO_ROOT,
    build_fixed_window_tsdf,
    build_scoring_tsdf,
    build_train_tsdf,
    load_final_data,
    parse_plan_date,
)
from .metrics import resolve_eval_metric
from .metrics.posthoc import PosthocInput, compute_posthoc_table

# ---------------------------------------------------------------------------
# Frozen / provisional controls (CONTROLS sheet mirrors these - see
# Code/common/update_plan_for_local.py, task 9)
# ---------------------------------------------------------------------------

RANDOM_SEED = 123
QUANTILE_LEVELS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
# num_val_windows is now DERIVED per-row from validation_periods/prediction_length (the
# plan's fixed-window restructure made it explicit per CONTROLS: "2 at every frequency").
# This constant is only a fallback for rows/callers that don't supply validation_periods.
NUM_VAL_WINDOWS = 2
# The Tab 5 pilot (11 origins, all 6 regimes) found 600s leaves 2 of 3 Chronos variants
# and even AutoCES unfitted (a real CONTROLS violation - "same pool everywhere"); 900s
# fit the complete declared pool in all 10 follow-up runs, with ~500s to spare. This is
# the settled value referenced by the fixed-window run - see Results/PILOT_FINDINGS_INTERIM.md.
TIME_LIMIT_S = 900
REFIT_FULL = False  # Frozen in CONTROLS 2026-09-22 (INDEX_SET_CHANGE.md "Experiment design
                     # - finalised"): every live block runs refit_full=False. The 24
                     # Tab01_HCPI_EM1 runs completed under True are retained, unmodified, as
                     # the refit_full=True arm of Block 0 (ARCHIVE_Superseded) - do not touch
                     # Results/Results_Tab01_HCPI_EM1.xlsx or its RunConfigs. See
                     # build_hyperparameters()/run_single_experiment() docstring below for
                     # what refit_full does and does not achieve given AutoGluon's per-model
                     # can_refit_full support.

CONFIG_DIR = REPO_ROOT / "Code" / "common"


def load_tab_controls(tab_name: str) -> dict:
    """Read Code/common/config_<tab_name>.yaml's `controls:` block (task 8: "reads the
    tab's YAML config"). The YAML is generated from the CONTROLS sheet by
    regenerate_configs.py, which is itself filled from the constants in this module
    (see update_plan_for_local.py) - so this is round-tripping the single source of
    truth through the workbook/YAML the rest of the plan's tooling expects to read,
    rather than tab scripts silently bypassing it.
    """
    path = CONFIG_DIR / f"config_{tab_name}.yaml"
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    controls = cfg.get("controls", {})
    # time_limit_s/num_val_windows/random_seed are written as plain numeric strings by
    # update_plan_for_local.py, but tolerate a stray non-digit suffix defensively rather
    # than crash on a hand-edited value.
    def _int(key: str, default: int) -> int:
        raw = str(controls.get(key, default))
        m = re.match(r"\s*(\d+)", raw)
        return int(m.group(1)) if m else default

    return {
        "time_limit": _int("time_limit_s", TIME_LIMIT_S),
        "num_val_windows": _int("num_val_windows", NUM_VAL_WINDOWS),
        "random_seed": _int("random_seed", RANDOM_SEED),
    }


# Pretrained variants and their real release dates (frozen facts, INDEX_SET_CHANGE.md).
# model_path values are AutoGluon's own registered aliases (verified against the
# installed 1.6.3 source: autogluon/timeseries/models/chronos/model.py MODEL_ALIASES).
PRETRAINED_VARIANTS = {
    "chronos_t5": {"hp_key": "Chronos", "model_path": "small", "release_date": pd.Timestamp("2024-03-01")},
    "chronos_bolt": {"hp_key": "Chronos", "model_path": "bolt_small", "release_date": pd.Timestamp("2024-11-01")},
    "chronos_2": {"hp_key": "Chronos2", "model_path": None, "release_date": pd.Timestamp("2025-10-01")},
}

# Explicit, fully-enumerated model pool - deliberately NOT one of AutoGluon's built-in
# presets (medium_quality pulls in Toto/Toto-2, which the frozen decision never named;
# CONTROLS requires the pool be identical and fully auditable across all tabs). DLinear
# added per the Set 1/2/3 restructure's explicit from-scratch deep-model list (PatchTST,
# TFT, DeepAR, TiDE, DLinear).
FROM_SCRATCH_HYPERPARAMETERS: dict = {
    "Naive": {}, "SeasonalNaive": {}, "Theta": {}, "AutoARIMA": {}, "AutoETS": {}, "AutoCES": {}, "NPTS": {},
    "DirectTabular": {}, "RecursiveTabular": {},
    "DeepAR": {}, "PatchTST": {}, "TemporalFusionTransformer": {}, "TiDE": {}, "DLinear": {},
}


def build_hyperparameters(include_pretrained: bool) -> dict:
    """include_pretrained=False (Sets 1 & 2) excludes Chronos/Chronos-Bolt/Chronos-2
    entirely - not merely down-weighted, absent from the hyperparameters dict passed to
    .fit(), so they cannot appear in the fitted leaderboard at all. include_pretrained=True
    (Set 3) adds them back. Verify the exclusion by inspecting the fitted leaderboard
    (predictor.info()['model_info'].keys()), not this function - the task's own
    instruction, and the right check since a config-level exclusion says what was
    *requested*, not what was *fit*.
    """
    hp = dict(FROM_SCRATCH_HYPERPARAMETERS)
    if include_pretrained:
        hp["Chronos"] = [
            {"model_path": PRETRAINED_VARIANTS["chronos_t5"]["model_path"]},
            {"model_path": PRETRAINED_VARIANTS["chronos_bolt"]["model_path"]},
        ]
        hp["Chronos2"] = {}
    return hp


def classify_model(model_name: str) -> tuple[str, str | None, pd.Timestamp | None]:
    """(family, variant, release_date) for a fitted model's name. Verified empirically
    against the installed package (see the P2-01 smoke test) rather than assumed from
    source reading alone.
    """
    if model_name.startswith("Chronos2"):
        v = PRETRAINED_VARIANTS["chronos_2"]
        return "pretrained-foundation", "chronos_2", v["release_date"]
    if model_name.startswith("Chronos"):
        if "bolt" in model_name.lower():
            v = PRETRAINED_VARIANTS["chronos_bolt"]
            return "pretrained-foundation", "chronos_bolt", v["release_date"]
        v = PRETRAINED_VARIANTS["chronos_t5"]
        return "pretrained-foundation", "chronos_t5", v["release_date"]
    if model_name == "WeightedEnsemble":
        return "ensemble", None, None
    return "trained-from-scratch", None, None


def release_position(horizon_start: pd.Timestamp, horizon_end: pd.Timestamp, release_date: pd.Timestamp) -> str:
    """Where this origin's horizon sits relative to one pretrained variant's release."""
    if horizon_end < release_date:
        return "fully_pre"
    if horizon_start >= release_date:
        return "fully_post"
    return "straddling"


@dataclass
class ExperimentResult:
    exp_id: str
    forecast_df: pd.DataFrame
    weights_df: pd.DataFrame
    posthoc_df: pd.DataFrame
    release_labels: dict
    metadata: dict
    runtime_sec: float
    run_config: dict


def run_single_experiment(
    exp_row: dict,
    eval_metric_code: str,
    time_limit: int = TIME_LIMIT_S,
    num_val_windows: int | None = None,
    random_seed: int = RANDOM_SEED,
    refit_full: bool = REFIT_FULL,
) -> ExperimentResult:
    """exp_row: one row of Code/experiments.csv as a dict - train_data_start,
    train_data_end, train_window_periods, validation_periods, pretrained_models all read
    from it, nothing hardcoded.

    FIXED ROLLING WINDOW (the expanding-window design is retired): training data is
    exactly [train_data_start, train_data_end], asserted to have train_window_periods
    rows - not "everything up to the cutoff".

    refit_full caveat, verified against the installed 1.6.3 source (trainer.py
    refit_single_full): AutoGluon's internal validation backtesting
    (ExpandingWindowSplitter, num_val_windows folds) means the model actually used for
    prediction - even nominally "the deployed model" - only ever trains on
    (train_window_periods - prediction_length) periods of the fixed window UNLESS
    refit_full=True AND the individual model type declares can_refit_full=True. Only
    two of this pool's models do (DirectTabular, RecursiveTabular - both mlforecast-
    based); every statistical and deep-learning model (Naive, Theta, AutoARIMA, AutoETS,
    AutoCES, NPTS, DeepAR, PatchTST, TemporalFusionTransformer, TiDE, DLinear, and
    Chronos/Chronos2 when included) gets a cheap rename-and-copy of the LAST validation
    window's model when refit_full=True, not a genuine retrain on the full window - this
    is a real AutoGluon architecture limitation, not a bug in this pipeline, and is
    recorded per-run in metadata/run_config so it can be cited as a manuscript caveat.
    refit_full=True is still enabled by default: it is a strict improvement for the two
    tabular models and a near-zero-cost no-op for everything else (confirmed empirically:
    the refit phase is not bound by time_limit and added a small constant overhead in
    testing, not a multiplier).
    """
    index = exp_row["index"]
    frequency = exp_row["frequency"]  # "Monthly"/"Quarterly"/"Annual"
    freq_key = FREQ_ALIAS[frequency]
    pandas_freq = FREQ_TO_PANDAS[freq_key]
    seasonal_period = FREQ_TO_SEASONAL_PERIOD[freq_key]

    train_data_start = parse_plan_date(exp_row["train_data_start"])
    train_data_end = parse_plan_date(exp_row["train_data_end"])
    horizon_start = parse_plan_date(exp_row["horizon_start"])
    horizon_end = parse_plan_date(exp_row["horizon_end"])
    prediction_length = int(exp_row["n_periods"])
    # experiments.csv's post-restructure schema splits what used to be one column into
    # train_periods + validation_periods = total_window (see INDEX_SET_CHANGE.md "Schema
    # changes"). train_data_start/train_data_end span the FULL total_window - AutoGluon's
    # own internal validation (num_val_windows folds via ExpandingWindowSplitter) is what
    # carves the trailing validation_periods out of that window, not an external split -
    # so total_window, not train_periods alone, is what gets asserted against the tsdf
    # row count and passed to predictor.fit().
    train_window_periods = int(exp_row["total_window"])
    validation_periods = int(exp_row["validation_periods"])
    if num_val_windows is None:
        num_val_windows = validation_periods // prediction_length
    include_pretrained = str(exp_row.get("pretrained_models", "No")).strip().lower() == "yes"

    # EM1 ("the winning metric") isn't chosen until Stage 2. Fit on MAE (EM2) instead
    # and record the substitution explicitly - never silently guess or crash.
    fitting_metric_code = eval_metric_code
    eval_metric_note = None
    if eval_metric_code == "EM1":
        fitting_metric_code = "EM2"
        eval_metric_note = (
            "EM1 (Stage-2 winning metric) not yet chosen; fit on EM2/MAE instead per instruction."
        )

    gpu_info = gpu.require_cuda()

    series = load_final_data(index, freq_key)
    train_tsdf = build_fixed_window_tsdf(
        series, train_data_start, train_data_end, item_id=index, expected_periods=train_window_periods
    )
    scoring_tsdf = build_scoring_tsdf(series, train_data_end, horizon_end, item_id=index)

    eval_metric = resolve_eval_metric(fitting_metric_code, prediction_length, seasonal_period)

    predictor = TimeSeriesPredictor(
        target="target",
        prediction_length=prediction_length,
        freq=pandas_freq,
        eval_metric=eval_metric,
        quantile_levels=QUANTILE_LEVELS,
        verbosity=1,
    )

    t0 = time.monotonic()
    predictor.fit(
        train_tsdf,
        hyperparameters=build_hyperparameters(include_pretrained=include_pretrained),
        time_limit=time_limit,
        num_val_windows=num_val_windows,
        random_seed=random_seed,
        refit_full=refit_full,
    )
    predictions = predictor.predict(train_tsdf)
    runtime_sec = time.monotonic() - t0

    # --- point + quantile forecast table ---
    pred_df = pd.DataFrame(predictions).reset_index()
    actual_h = scoring_tsdf.loc[(index, slice(None)), "target"].to_numpy()[-prediction_length:]
    pred_df["actual"] = actual_h
    pred_df = pred_df.rename(columns={"timestamp": "date"}).drop(columns=["item_id"])

    # --- ensemble weights, every fitted model, tagged by family/variant/release ---
    # Prefer the "_FULL" ensemble when refit_full produced one - THAT is the ensemble
    # predictor.predict() actually used (predictor.model_best is updated to point at it).
    info = predictor.info()
    model_info = info.get("model_info", {})
    has_full = "WeightedEnsemble_FULL" in model_info
    ensemble_key = "WeightedEnsemble_FULL" if has_full else "WeightedEnsemble"
    excluded = {"WeightedEnsemble", "WeightedEnsemble_FULL"}
    all_model_names = [m for m in model_info.keys() if m not in excluded]
    if has_full:
        full_names = [m for m in all_model_names if m.endswith("_FULL")]
        all_model_names = full_names or all_model_names  # fall back if refit skipped a model
    if ensemble_key in model_info:
        weights = model_info[ensemble_key].get("model_weights", {})
    elif len(all_model_names) == 1:
        # Time budget only allowed one model to fit at all - no ensemble was formed,
        # but that one model IS the (trivial) ensemble, weight 1.0, not 0.0.
        weights = {all_model_names[0]: 1.0}
    else:
        weights = {}
    weight_rows = []
    for name in all_model_names:
        base_name = name[: -len("_FULL")] if name.endswith("_FULL") else name
        family, variant, release_date = classify_model(base_name)
        weight_rows.append({
            "model": name, "family": family, "variant": variant,
            "release_date": release_date.date().isoformat() if release_date is not None else None,
            "weight": weights.get(name, 0.0),
        })
    weights_df = pd.DataFrame(weight_rows).sort_values("weight", ascending=False).reset_index(drop=True)

    # --- release-date origin labels (task 7) ---
    release_labels = {
        variant: release_position(horizon_start, horizon_end, v["release_date"])
        for variant, v in PRETRAINED_VARIANTS.items()
    }

    # --- post-hoc metrics on level / period-on-period / year-on-year ---
    past_values = train_tsdf["target"].to_numpy()
    forecast_h = pred_df["mean"].to_numpy()
    quantiles_h = {q: pred_df[q].to_numpy() for q in [str(x) for x in QUANTILE_LEVELS] if q in pred_df.columns}
    posthoc_input = PosthocInput(
        past_dates=pd.DatetimeIndex(train_tsdf.index.get_level_values("timestamp")),
        past_values=past_values,
        horizon_dates=pd.DatetimeIndex(pred_df["date"]),
        actual_h=actual_h,
        forecast_h=forecast_h,
        seasonal_period=seasonal_period,
        quantiles_h=quantiles_h or None,
    )
    posthoc_df = compute_posthoc_table(posthoc_input)

    metadata = {
        "exp_id": exp_row["exp_id"],
        "tab_name": exp_row["tab_name"],
        "index": index,
        "frequency": frequency,
        "eval_metric_code_plan": eval_metric_code,
        "eval_metric_code_fitted": fitting_metric_code,
        "eval_metric_note": eval_metric_note,
        "train_data_start": train_data_start.date().isoformat(),
        "train_data_end": train_data_end.date().isoformat(),
        "train_window_periods": train_window_periods,
        "train_rows_actual": len(train_tsdf),
        "horizon_start": horizon_start.date().isoformat(),
        "horizon_end": horizon_end.date().isoformat(),
        "n_periods": prediction_length,
        "include_pretrained_models": include_pretrained,
        "refit_full_enabled": refit_full,
        "refit_full_produced_full_models": has_full,
        "deployed_model": predictor.model_best,
        "refit_full_caveat": (
            "Only DirectTabular/RecursiveTabular genuinely retrain on the full "
            f"{train_window_periods}-period window under refit_full (can_refit_full=True); "
            "every other model (statistical + deep-learning + Chronos family) is a "
            f"rename-copy of the last internal validation window's model, which trained "
            f"on {train_window_periods - validation_periods // num_val_windows} periods "
            "- an AutoGluon architecture limitation, not a pipeline bug."
        ),
        "runtime_sec": round(runtime_sec, 2),
        **gpu_info.as_dict(),
        "autogluon_timeseries_version": agts.__version__,
        "random_seed": random_seed,
        "time_limit_s": time_limit,
        "num_val_windows": num_val_windows,
        "validation_periods": validation_periods,
    }

    run_config = {
        **metadata,
        "model_pool_requested": {
            k: v for k, v in build_hyperparameters(include_pretrained=include_pretrained).items()
        },
        "model_pool_fitted": all_model_names,
        "quantile_levels": QUANTILE_LEVELS,
        "target_transformation": "index level, 2021=100 (frozen decision)",
    }

    return ExperimentResult(
        exp_id=exp_row["exp_id"],
        forecast_df=pred_df,
        weights_df=weights_df,
        posthoc_df=posthoc_df,
        release_labels=release_labels,
        metadata=metadata,
        runtime_sec=runtime_sec,
        run_config=run_config,
    )
