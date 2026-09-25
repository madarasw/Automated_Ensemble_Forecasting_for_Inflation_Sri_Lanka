"""Post-hoc metric reporting: EM2-EM18 computed on three representations of a finished
forecast - level, period-on-period % change (month-on-month for monthly data,
quarter-on-quarter for quarterly), and year-on-year % change.

This governs what gets REPORTED for Phase 4. It is deliberately separate from the
internal transform in temporal.py/directional.py, which governs what the ensemble
FITTING objective optimises (always YoY for EM12-EM18, per the task instruction).

Design: native metrics (EM2-EM11) are AutoGluon's own scorer classes, instantiated
directly and called on purpose-built single-item TimeSeriesDataFrames - this reuses
AutoGluon's exact formulas (no hand-rolled reimplementation that could subtly diverge)
and its real save_past_metrics/compute_metric split for the scale-dependent ones (MASE,
RMSSE). Custom metrics (EM12-EM18) call the plain numpy functions in temporal.py/
directional.py directly on whichever representation's (actual, forecast) arrays are
asked for - those functions are representation-agnostic by construction, so calling them
on a level/MoM/YoY pair is unambiguous and never double-transforms.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from autogluon.timeseries import TimeSeriesDataFrame
from autogluon.timeseries.metrics import AVAILABLE_METRICS

from .directional import directional_accuracy, trend_direction_accuracy, turning_point_accuracy
from .temporal import _dtw_path_and_cost, soft_dtw_distance, tdi_distance, wasserstein_2d_time_value

NATIVE_EM = {
    "EM2": "MAE", "EM3": "RMSE", "EM4": "MAPE", "EM5": "SMAPE", "EM6": "MASE",
    "EM7": "RMSSE", "EM8": "WAPE", "EM9": "WQL", "EM10": "SQL", "EM11": "MQL",
}
QUANTILE_EM = {"EM9", "EM10", "EM11"}
CUSTOM_EM = {"EM12", "EM13", "EM14", "EM15", "EM16", "EM17", "EM18"}
REPRESENTATIONS = ("level", "period_on_period", "year_on_year")


@dataclass
class PosthocInput:
    """Everything needed to score one experiment's finished forecast on all three
    representations. `past_values`/`past_dates` cover series-start..train_data_end
    inclusive; `actual_h`/`forecast_h`/`horizon_dates` cover the prediction_length
    horizon. `quantiles_h`, if given, maps quantile-level string ("0.1", ...) to a
    length-prediction_length array.
    """
    past_dates: pd.DatetimeIndex
    past_values: np.ndarray
    horizon_dates: pd.DatetimeIndex
    actual_h: np.ndarray
    forecast_h: np.ndarray
    seasonal_period: int  # 12 monthly, 4 quarterly, 1 annual
    quantiles_h: dict[str, np.ndarray] | None = None


def _pct_change_series(values: np.ndarray, lag: int) -> np.ndarray:
    """(v[t]/v[t-lag]-1)*100, NaN where t<lag (not enough history)."""
    out = np.full(len(values), np.nan)
    if lag < len(values):
        out[lag:] = (values[lag:] / values[:-lag] - 1.0) * 100.0
    return out


def _transform_representation(inp: PosthocInput, representation: str):
    """Returns (past_transformed, actual_h_transformed, forecast_h_transformed) as
    1-D arrays aligned to (past_dates, horizon_dates) minus any NaN warm-up rows that
    a period-on-period/YoY transform introduces at series start (dropped, not filled)."""
    if representation == "level":
        return inp.past_values, inp.actual_h, inp.forecast_h

    lag = 1 if representation == "period_on_period" else inp.seasonal_period
    if lag <= 1 and representation == "year_on_year":
        # Annual frequency: YoY is not a meaningful transform (see _yoy.py docstring).
        return inp.past_values, inp.actual_h, inp.forecast_h

    full_actual = np.concatenate([inp.past_values, inp.actual_h])
    full_forecast_context = np.concatenate([inp.past_values, inp.forecast_h])
    past_t = _pct_change_series(inp.past_values, lag)
    actual_h_t = _pct_change_series(full_actual, lag)[-len(inp.actual_h):]
    forecast_h_t = _pct_change_series(full_forecast_context, lag)[-len(inp.forecast_h):]
    # Drop the NaN warm-up in the past segment only; horizon segment is always fully
    # computable since prediction_length == seasonal_period in every tab of this plan.
    past_t = past_t[~np.isnan(past_t)]
    return past_t, actual_h_t, forecast_h_t


def _native_metric_value(em_code: str, past: np.ndarray, actual_h: np.ndarray, forecast_h: np.ndarray,
                          seasonal_period: int, quantiles_h: dict[str, np.ndarray] | None) -> float | None:
    metric_name = NATIVE_EM[em_code]
    if em_code in QUANTILE_EM and not quantiles_h:
        return None  # not computed - no quantile forecast recorded for this experiment

    h = len(actual_h)
    dates = pd.date_range("2000-01-01", periods=len(past) + h, freq="MS")
    past_dates, horizon_dates = dates[:len(past)], dates[len(past):]

    data_df = pd.DataFrame({
        "item_id": "series", "timestamp": dates,
        "target": np.concatenate([past, actual_h]),
    })
    data_tsdf = TimeSeriesDataFrame.from_data_frame(data_df)

    pred_cols = {"item_id": "series", "timestamp": horizon_dates, "mean": forecast_h}
    if quantiles_h:
        pred_cols.update(quantiles_h)
    predictions = TimeSeriesDataFrame.from_data_frame(pd.DataFrame(pred_cols))

    scorer_cls = AVAILABLE_METRICS[metric_name]
    scorer = scorer_cls(prediction_length=h, seasonal_period=max(seasonal_period, 1))
    # AutoGluon's TimeSeriesScorer.__call__ returns metric_value * scorer.sign, flipping
    # loss-type metrics (MAE, RMSE, ...) negative so every metric is uniformly
    # "higher is better" for its own internal model selection (verified against the
    # installed 1.6.3 source: autogluon/timeseries/metrics/abstract.py). Multiplying by
    # scorer.sign again undoes that flip (sign is +-1) so this table reports metrics in
    # their natural sign for human/paper reading - MAE/RMSE/... as non-negative losses.
    return float(scorer(data=data_tsdf, predictions=predictions, target="target") * scorer.sign)


def _custom_metric_value(em_code: str, past: np.ndarray, actual_h: np.ndarray, forecast_h: np.ndarray) -> float | None:
    if em_code == "EM12":
        dist, _ = _dtw_path_and_cost(actual_h, forecast_h)
        return dist
    if em_code == "EM13":
        return soft_dtw_distance(actual_h, forecast_h, gamma=1.0)
    if em_code == "EM14":
        return wasserstein_2d_time_value(actual_h, forecast_h)
    if em_code == "EM15":
        return tdi_distance(actual_h, forecast_h)
    if len(past) == 0:
        return None  # no origin anchor available (e.g. level representation has no natural "origin rate")
    origin = past[-1]
    if em_code == "EM16":
        return 1.0 - trend_direction_accuracy(origin, actual_h, forecast_h)
    if em_code == "EM17":
        return 1.0 - directional_accuracy(origin, actual_h, forecast_h)
    if em_code == "EM18":
        actual_seq = np.concatenate([[origin], actual_h])
        forecast_seq = np.concatenate([[origin], forecast_h])
        tpa, _had_tp = turning_point_accuracy(actual_seq, forecast_seq)
        return 1.0 - tpa
    raise ValueError(em_code)


def compute_posthoc_table(inp: PosthocInput) -> pd.DataFrame:
    """Returns a tidy DataFrame: columns [em_code, metric_name, representation, value],
    18 EM codes x 3 representations = 54 rows (fewer if quantile/origin-dependent
    entries are not computable for a given representation - those rows carry value=NaN
    with the reason implicit from em_code/representation, never a fabricated number).
    """
    rows = []
    for representation in REPRESENTATIONS:
        past_t, actual_t, forecast_t = _transform_representation(inp, representation)
        for em_code, name in NATIVE_EM.items():
            val = _native_metric_value(em_code, past_t, actual_t, forecast_t, inp.seasonal_period,
                                         inp.quantiles_h if representation == "level" else None)
            rows.append({"em_code": em_code, "metric_name": name, "representation": representation, "value": val})
        for em_code in sorted(CUSTOM_EM):
            val = _custom_metric_value(em_code, past_t, actual_t, forecast_t)
            rows.append({"em_code": em_code, "metric_name": em_code, "representation": representation, "value": val})
    return pd.DataFrame(rows)
