"""Shared machinery for the temporal/directional scorers: internal conversion of an
index-level series to year-on-year (monthly: 12-period lag; quarterly: 4-period lag)
percent change, computed using ONLY values available before the forecast horizon.

Design note. AutoGluon's TimeSeriesScorer.__call__ (confirmed against the installed
1.6.3 source) splits its input into data_past/data_future and calls
save_past_metrics(data_past, ...) BEFORE compute_metric(data_future, predictions, ...) -
the same mechanism MASE uses internally for its scale factor. This mixin uses exactly
that mechanism, so no leakage is possible: only data_past ever backs the lag lookup, and
for a prediction_length == seasonal_period horizon (true for every tab in this plan:
12-month or 4-quarter horizons), the value 12/4 periods before ANY forecasted point is
always inside data_past, never inside data_future.
"""
from __future__ import annotations

import numpy as np


class YoYTransformMixin:
    """Mixin for TimeSeriesScorer subclasses that must score on the year-on-year (or
    quarter-on-quarter) transform rather than the raw index level. Subclasses must NOT
    override save_past_metrics/clear_past_metrics; implement compute_metric and call
    self._yoy_arrays(data_future, predictions, target) to get the transformed arrays.
    """

    def save_past_metrics(self, data_past, target: str = "target", seasonal_period: int = 1, **kwargs) -> None:
        self._past_target = data_past[target]
        self._lag = max(int(seasonal_period), 1)

    def clear_past_metrics(self) -> None:
        self._past_target = None
        self._lag = None

    def _yoy_arrays(self, data_future, predictions, target: str = "target") -> tuple[np.ndarray, np.ndarray]:
        """Returns (yoy_true, yoy_pred), 1-D numpy arrays of length prediction_length,
        for a single-item series. This study never scores multi-item panels (one
        forecast origin = one index = one series), so multi-item input is rejected
        rather than silently aggregated.

        At annual frequency (seasonal_period <= 1) a period-over-period transform is
        not a meaningful "year-on-year" rate, so this falls back to the level itself -
        a documented limitation, not a silently fabricated number.
        """
        item_ids = list(data_future.item_ids)
        if len(item_ids) != 1:
            raise NotImplementedError(
                f"YoY-internal scorers are only implemented for single-item series; got {len(item_ids)} items."
            )
        item_id = item_ids[0]

        future_true = data_future[target].xs(item_id, level="item_id").sort_index()
        future_pred = predictions["mean"].xs(item_id, level="item_id").sort_index()
        h = len(future_true)

        if self._lag <= 1:
            return future_true.to_numpy(dtype=float), future_pred.to_numpy(dtype=float)

        past = self._past_target.xs(item_id, level="item_id").sort_index()
        if len(past) < self._lag:
            raise ValueError(
                f"Need at least {self._lag} past periods for the internal YoY transform, got {len(past)}."
            )
        if h > self._lag:
            raise NotImplementedError(
                f"prediction_length ({h}) exceeds seasonal_period ({self._lag}); the lag lookup for steps "
                "beyond the first seasonal_period would fall inside the forecast horizon itself, which this "
                "implementation does not support (no tab in the current plan needs it: every horizon length "
                "equals its own frequency's seasonal period)."
            )

        base = past.to_numpy(dtype=float)[-self._lag:][:h]
        yoy_true = (future_true.to_numpy(dtype=float) / base - 1.0) * 100.0
        yoy_pred = (future_pred.to_numpy(dtype=float) / base - 1.0) * 100.0
        return yoy_true, yoy_pred

    def _yoy_origin_anchor(self) -> float:
        """The YoY rate at the forecast origin (train_data_end) itself - the anchor
        TDA compares against. Requires 2*lag past periods (one full extra year before
        the lag window) - always true at every origin in this plan (shortest history is
        72 months at the first monthly origin, lag=12).
        """
        if self._lag <= 1:
            raise NotImplementedError("Origin-anchor YoY is undefined at annual frequency (lag<=1).")
        past = list(self._past_target.groupby(level="item_id"))[0][1].sort_index().to_numpy(dtype=float)
        if len(past) < 2 * self._lag:
            raise ValueError(
                f"Need at least {2 * self._lag} past periods to compute the origin's own YoY rate, "
                f"got {len(past)}."
            )
        latest = past[-1]
        year_ago = past[-1 - self._lag]
        return (latest / year_ago - 1.0) * 100.0
