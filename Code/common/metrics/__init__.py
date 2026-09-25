"""Registry mapping EM codes to TimeSeriesScorer classes/instances.

EM2-EM11 are AutoGluon-native (point + probabilistic metrics) and referenced by their
built-in string names. EM12-EM18 are the custom scorers implemented in this package.
"""
from __future__ import annotations

from autogluon.timeseries.metrics import TimeSeriesScorer

from .directional import DAScorer, TDAScorer, TPAScorer
from .temporal import DTWScorer, SoftDTWScorer, TDIScorer, WassersteinScorer

# AutoGluon's own names for the native metrics (verified against the installed 1.6.3
# metrics registry - see autogluon.timeseries.metrics for the canonical list).
NATIVE_METRIC_NAME = {
    "EM2": "MAE",
    "EM3": "RMSE",
    "EM4": "MAPE",
    "EM5": "SMAPE",
    "EM6": "MASE",
    "EM7": "RMSSE",
    "EM8": "WAPE",
    "EM9": "WQL",
    "EM10": "SQL",
    "EM11": "MQL",
}

CUSTOM_SCORER_CLASS: dict[str, type[TimeSeriesScorer]] = {
    "EM12": DTWScorer,
    "EM13": SoftDTWScorer,
    "EM14": WassersteinScorer,
    "EM15": TDIScorer,
    "EM16": TDAScorer,
    "EM17": DAScorer,
    "EM18": TPAScorer,
}

ALL_EM_CODES = [f"EM{i}" for i in range(2, 19)]


def resolve_eval_metric(em_code: str, prediction_length: int, seasonal_period: int):
    """Returns the object to pass as TimeSeriesPredictor(eval_metric=...) for a given
    EM code - a string for native metrics, an instantiated custom scorer otherwise.
    """
    if em_code in NATIVE_METRIC_NAME:
        return NATIVE_METRIC_NAME[em_code]
    if em_code in CUSTOM_SCORER_CLASS:
        cls = CUSTOM_SCORER_CLASS[em_code]
        return cls(prediction_length=prediction_length, seasonal_period=seasonal_period)
    raise ValueError(f"Unknown EM code: {em_code!r}")


def all_posthoc_scorers(prediction_length: int, seasonal_period: int) -> dict[str, object]:
    """One instance per EM2-EM18, for predictor.evaluate(data, metrics=[...])-style
    post-hoc scoring. Native metrics are returned as their string names (evaluate()
    accepts a mix of strings and TimeSeriesScorer instances)."""
    out: dict[str, object] = {}
    for code, name in NATIVE_METRIC_NAME.items():
        out[code] = name
    for code, cls in CUSTOM_SCORER_CLASS.items():
        out[code] = cls(prediction_length=prediction_length, seasonal_period=seasonal_period)
    return out
