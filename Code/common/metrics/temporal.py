"""Temporal-similarity scorers (EM12-EM15): DTW, Soft-DTW, Wasserstein, TDI.

None of these is AutoGluon-native (confirmed: not in the model registry's built-in
metrics list). All four convert to year-on-year percent change internally before
scoring (via YoYTransformMixin) - scoring these on a monotone-rising index level would
be close to meaningless, since DTW/TDI measure temporal *shape* and a near-straight
rising line has almost no shape to distinguish between a good and bad forecast.
"""
from __future__ import annotations

import numpy as np
from autogluon.timeseries.metrics import TimeSeriesScorer
from scipy.optimize import linear_sum_assignment
from scipy.stats import wasserstein_distance

from ._yoy import YoYTransformMixin


def _dtw_path_and_cost(a: np.ndarray, b: np.ndarray) -> tuple[float, list[tuple[int, int]]]:
    """Classic DTW: dynamic-programming alignment with absolute-difference local cost,
    no bandwidth constraint (series are 12 points at most - full DP is cheap and exact).
    Citation: Sakoe, H., & Chiba, S. (1978). "Dynamic programming algorithm optimization
    for spoken word recognition." IEEE Trans. ASSP, 26(1), 43-49.
    """
    n, m = len(a), len(b)
    cost = np.abs(a[:, None] - b[None, :])
    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = cost[i - 1, j - 1] + min(D[i - 1, j - 1], D[i - 1, j], D[i, j - 1])

    i, j = n, m
    path: list[tuple[int, int]] = []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        choices = [(D[i - 1, j - 1], i - 1, j - 1), (D[i - 1, j], i - 1, j), (D[i, j - 1], i, j - 1)]
        _, i, j = min(choices, key=lambda c: c[0])
    path.reverse()
    return float(D[n, m]), path


def _softmin(values: np.ndarray, gamma: float) -> float:
    z = -values / gamma
    zmax = np.max(z)
    return float(-gamma * (zmax + np.log(np.sum(np.exp(z - zmax)))))


def soft_dtw_distance(a: np.ndarray, b: np.ndarray, gamma: float = 1.0) -> float:
    """Soft-DTW with squared-Euclidean local cost (the convention used in the original
    paper's reference implementation) and fixed gamma.
    Citation: Cuturi, M., & Blondel, M. (2017). "Soft-DTW: a Differentiable Loss
    Function for Time-Series." ICML 2017, PMLR 70:894-903.
    """
    n, m = len(a), len(b)
    cost = (a[:, None] - b[None, :]) ** 2
    R = np.full((n + 1, m + 1), np.inf)
    R[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            R[i, j] = cost[i - 1, j - 1] + _softmin(
                np.array([R[i - 1, j - 1], R[i - 1, j], R[i, j - 1]]), gamma
            )
    return float(R[n, m])


def tdi_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Temporal Distortion Index, computed from the DTW optimal path.

    Citation (concept): Frias-Paredes, L., Mallor, F., Leon, T., & Gaston-Romeo, M.
    (2016). "Introducing the Temporal Distortion Index to perform a bidimensional
    analysis of renewable energy forecast." Energy, 94(1), 180-194.

    Implementation note: the original paper's exact normalisation is behind a paywall.
    This implements the standard computable reformulation used in the follow-on
    DTW/shape-and-time literature (e.g. the DILATE loss decomposition): TDI is the
    path's total squared temporal displacement from the identity diagonal, (i-j)^2
    summed over the optimal path, divided by (n-1)^2 * len(path) as a conservative
    upper-bound normaliser so the statistic falls in [0, 1] (0 = no temporal distortion,
    values near 1 = a maximally displaced alignment). This normaliser is a documented
    approximation, not a verbatim transcription of the original paper's constant.
    """
    n = len(a)
    _, path = _dtw_path_and_cost(a, b)
    if n <= 1:
        return 0.0
    raw = sum((i - j) ** 2 for i, j in path)
    denom = (n - 1) ** 2 * len(path)
    return float(raw / denom) if denom > 0 else 0.0


def wasserstein_1d(a: np.ndarray, b: np.ndarray) -> float:
    """1-D Wasserstein distance between the VALUE distributions of a and b, ignoring
    time order entirely - permutation-invariant (shuffling either series in time does
    not change this number). Provided for the task 6d demonstration; not the
    recommended default.
    """
    return float(wasserstein_distance(a, b))


def wasserstein_2d_time_value(a: np.ndarray, b: np.ndarray) -> float:
    """Wasserstein distance between the (time, value) point clouds of a and b: each
    series is treated as n equally-weighted points in the plane (index position,
    value), and the exact discrete optimal-transport cost (here, n=n so this is exact
    bipartite assignment, solved with the Hungarian algorithm - no approximation needed
    for a 12-point series) under squared-Euclidean ground cost.

    Caveat documented deliberately: "index position" (0..n-1, unitless step count) and
    "value" (percentage points, after the internal YoY transform) are on different
    scales, and this implementation does not attempt to renormalise them onto a common
    scale - the two axes are compared as raw numbers. This is a modelling choice, not a
    hidden default; task 6d's ruling should state whether a rescaling is wanted.
    """
    n = len(a)
    pts_a = np.column_stack([np.arange(n, dtype=float), a])
    pts_b = np.column_stack([np.arange(n, dtype=float), b])
    cost = ((pts_a[:, None, :] - pts_b[None, :, :]) ** 2).sum(axis=2)
    row_ind, col_ind = linear_sum_assignment(cost)
    return float(cost[row_ind, col_ind].sum() / n)


class DTWScorer(YoYTransformMixin, TimeSeriesScorer):
    """EM12."""
    greater_is_better_internal = False
    optimum = 0.0

    def compute_metric(self, data_future, predictions, target: str = "target", **kwargs) -> float:
        yoy_true, yoy_pred = self._yoy_arrays(data_future, predictions, target)
        dist, _ = _dtw_path_and_cost(yoy_true, yoy_pred)
        return dist


class SoftDTWScorer(YoYTransformMixin, TimeSeriesScorer):
    """EM13. gamma fixed at 1.0 - do not vary across tabs (task instruction)."""
    greater_is_better_internal = False
    optimum = 0.0
    GAMMA = 1.0

    def compute_metric(self, data_future, predictions, target: str = "target", **kwargs) -> float:
        yoy_true, yoy_pred = self._yoy_arrays(data_future, predictions, target)
        return soft_dtw_distance(yoy_true, yoy_pred, gamma=self.GAMMA)


class WassersteinScorer(YoYTransformMixin, TimeSeriesScorer):
    """EM14. Uses the 2-D (time, value) formulation by default - see task 6d /
    METRIC_RULINGS.md for the 1-D vs 2-D judgement call this is provisional on.
    """
    greater_is_better_internal = False
    optimum = 0.0
    USE_2D = True

    def compute_metric(self, data_future, predictions, target: str = "target", **kwargs) -> float:
        yoy_true, yoy_pred = self._yoy_arrays(data_future, predictions, target)
        if self.USE_2D:
            return wasserstein_2d_time_value(yoy_true, yoy_pred)
        return wasserstein_1d(yoy_true, yoy_pred)


class TDIScorer(YoYTransformMixin, TimeSeriesScorer):
    """EM15."""
    greater_is_better_internal = False
    optimum = 0.0

    def compute_metric(self, data_future, predictions, target: str = "target", **kwargs) -> float:
        yoy_true, yoy_pred = self._yoy_arrays(data_future, predictions, target)
        return tdi_distance(yoy_true, yoy_pred)
