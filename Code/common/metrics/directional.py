"""Directional scorers (EM16-EM18): TDA, DA, TPA.

All three convert to year-on-year percent change internally (via YoYTransformMixin)
before scoring - on the raw rising index level, "up" is almost always the right call
and these metrics would be degenerate (see METRICS sheet / task framing).

TDA vs DA (the METRICS sheet flags these as "routinely conflated" and asks for the
exact distinction used here):
  - DA  (EM17): STEP-TO-STEP direction. Is sign(x[h]-x[h-1]) right, at each h?
                Classic directional-accuracy formulation; see Pesaran & Timmermann
                (1992), "A Simple Nonparametric Test of Predictive Performance",
                Journal of Business & Economic Statistics, 10(4), 461-465.
  - TDA (EM16): ORIGIN-RELATIVE direction. Is sign(x[h]-x[origin]) right, at each h?
                A coarser, more forgiving notion of "did we call the overall trend".
Both reduce to "how many of h=1..12 were called right" (0-12, 13 distinct values) -
matches the METRICS sheet's coarseness warning regardless of which definition is used.

Tie-break default (task 6c, provisional): a sign comparison counts as a match only if
BOTH signs are exactly equal, including the zero case (flat vs flat = match; flat vs
any nonzero = no match). METRIC_RULINGS.md reports how often ties actually occur in the
real data before asking this to be ratified.
"""
from __future__ import annotations

import numpy as np
from autogluon.timeseries.metrics import TimeSeriesScorer

from ._yoy import YoYTransformMixin

TPA_TOLERANCE = 1  # periods; see task 6b


def _turning_points(seq: np.ndarray) -> list[int]:
    """Strict local extrema (interior points only) in `seq`.

    Adapted from Bry, G., & Boschan, C. (1971), "Cyclical Analysis of Time Series:
    Selected Procedures and Computer Programs", NBER - the standard reference for
    turning-point dating (used in NBER/CEPR business-cycle dating). Simplified here:
    the original's minimum-phase-length rule is dropped because it is designed for
    long series and has no sensible operating point on a 12-step horizon.
    """
    tp = []
    for i in range(1, len(seq) - 1):
        if (seq[i] > seq[i - 1] and seq[i] > seq[i + 1]) or (seq[i] < seq[i - 1] and seq[i] < seq[i + 1]):
            tp.append(i)
    return tp


def turning_point_accuracy(
    actual_seq: np.ndarray, forecast_seq: np.ndarray, tolerance: int = TPA_TOLERANCE
) -> tuple[float, bool]:
    """actual_seq/forecast_seq must include the origin's own YoY value at index 0, so
    interior indices 1..h are the horizon steps (this lets a turning point AT the first
    horizon step be detected against the origin).

    Returns (TPA, had_turning_points). TPA = fraction of ACTUAL turning points also
    flagged by the forecast within `tolerance` periods. If there are no actual turning
    points, returns (0.5, False) - the documented default fallback (task 6b), a neutral
    "no information" value rather than crashing model selection; had_turning_points=False
    lets callers tally the real UNDEFINED rate for METRIC_RULINGS.md.
    """
    actual_tp = _turning_points(actual_seq)
    if not actual_tp:
        return 0.5, False
    forecast_tp = _turning_points(forecast_seq)
    hits = sum(1 for t in actual_tp if any(abs(t - f) <= tolerance for f in forecast_tp))
    return hits / len(actual_tp), True


def trend_direction_accuracy(origin: float, actual_h: np.ndarray, forecast_h: np.ndarray) -> float:
    """TDA: origin-relative sign agreement, averaged over h=1..len(actual_h)."""
    actual_sign = np.sign(actual_h - origin)
    forecast_sign = np.sign(forecast_h - origin)
    return float(np.mean(actual_sign == forecast_sign))


def directional_accuracy(origin: float, actual_h: np.ndarray, forecast_h: np.ndarray) -> float:
    """DA: step-to-step sign agreement (each series compared against its own previous
    value; h=1 compared against the origin), averaged over h=1..len(actual_h)."""
    actual_prev = np.concatenate([[origin], actual_h[:-1]])
    forecast_prev = np.concatenate([[origin], forecast_h[:-1]])
    actual_sign = np.sign(actual_h - actual_prev)
    forecast_sign = np.sign(forecast_h - forecast_prev)
    return float(np.mean(actual_sign == forecast_sign))


class TDAScorer(YoYTransformMixin, TimeSeriesScorer):
    """EM16. Loss form: 1 - TDA (0 = perfect), so lower is better like every other
    scorer in this codebase."""
    greater_is_better_internal = False
    optimum = 0.0

    def compute_metric(self, data_future, predictions, target: str = "target", **kwargs) -> float:
        yoy_true, yoy_pred = self._yoy_arrays(data_future, predictions, target)
        origin = self._yoy_origin_anchor()
        return 1.0 - trend_direction_accuracy(origin, yoy_true, yoy_pred)


class DAScorer(YoYTransformMixin, TimeSeriesScorer):
    """EM17."""
    greater_is_better_internal = False
    optimum = 0.0

    def compute_metric(self, data_future, predictions, target: str = "target", **kwargs) -> float:
        yoy_true, yoy_pred = self._yoy_arrays(data_future, predictions, target)
        origin = self._yoy_origin_anchor()
        return 1.0 - directional_accuracy(origin, yoy_true, yoy_pred)


class TPAScorer(YoYTransformMixin, TimeSeriesScorer):
    """EM18. `last_had_turning_point` records whether the most recent compute_metric
    call found any actual turning points, for diagnostics/METRIC_RULINGS.md tallying."""
    greater_is_better_internal = False
    optimum = 0.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_had_turning_point: bool | None = None

    def compute_metric(self, data_future, predictions, target: str = "target", **kwargs) -> float:
        yoy_true, yoy_pred = self._yoy_arrays(data_future, predictions, target)
        origin = self._yoy_origin_anchor()
        actual_seq = np.concatenate([[origin], yoy_true])
        forecast_seq = np.concatenate([[origin], yoy_pred])
        tpa, had_tp = turning_point_accuracy(actual_seq, forecast_seq)
        self.last_had_turning_point = had_tp
        return 1.0 - tpa
