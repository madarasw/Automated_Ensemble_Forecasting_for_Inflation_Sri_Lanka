"""Hand-worked examples for all seven custom metrics (P2-05). Every expected value here
is derived by hand-tracing the algorithm (shown in comments), not by running the code
and copying its output - a metric you cannot define precisely is one a reviewer can
dismiss.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from Code.common.metrics.directional import (
    directional_accuracy,
    trend_direction_accuracy,
    turning_point_accuracy,
)
from Code.common.metrics.temporal import (
    _dtw_path_and_cost,
    soft_dtw_distance,
    tdi_distance,
    wasserstein_1d,
    wasserstein_2d_time_value,
)


# ---------------------------------------------------------------------------
# DTW (EM12)
# ---------------------------------------------------------------------------

def test_dtw_identical_series_is_zero():
    a = np.array([1.0, 2.0, 3.0])
    dist, path = _dtw_path_and_cost(a, a.copy())
    assert dist == 0.0
    assert path == [(0, 0), (1, 1), (2, 2)]


def test_dtw_constant_offset():
    # cost[i][j] = |0-1| = 1 for every cell (3x3, all ones). The cheapest monotonic
    # path from (0,0) to (2,2) has exactly 3 cells (the diagonal) - no path can use
    # fewer than 3 cells and reach the corner, so the minimum achievable total is
    # 3 * 1 = 3. Hand-traced DP confirms the diagonal is in fact optimal (every other
    # path revisits a row/column, adding cells without reducing per-cell cost, since
    # all cells cost exactly 1).
    a = np.array([0.0, 0.0, 0.0])
    b = np.array([1.0, 1.0, 1.0])
    dist, path = _dtw_path_and_cost(a, b)
    assert dist == pytest.approx(3.0)
    assert path == [(0, 0), (1, 1), (2, 2)]


# ---------------------------------------------------------------------------
# Soft-DTW (EM13), gamma = 1.0
# ---------------------------------------------------------------------------

def test_soft_dtw_hand_traced_2x2():
    # a=[0,1], b=[0,1], gamma=1. cost = squared diff = [[0,1],[1,0]].
    # R[1,1] = cost[0,0] + softmin(R[0,0]=0, inf, inf) = 0 + 0 = 0
    #   (softmin_1(0,inf,inf) = -log(e^0 + 0 + 0) = -log(1) = 0)
    # R[1,2] = cost[0,1] + softmin(inf, R[0,1]=inf... wait indices: uses R[0,1],R[0,2]? )
    # Recurrence used by the implementation: R[i,j] = cost[i-1,j-1] +
    #   softmin(R[i-1,j-1], R[i-1,j], R[i,j-1])
    # R[1,2] = cost[0,1] + softmin(R[0,1]=inf, R[0,2]=inf, R[1,1]=0) = 1 + 0 = 1
    # R[2,1] = cost[1,0] + softmin(R[1,0]=inf, R[1,1]=0, R[2,0]=inf) = 1 + 0 = 1
    # R[2,2] = cost[1,1] + softmin(R[1,1]=0, R[1,2]=1, R[2,1]=1)
    #        = 0 + (-log(e^0 + e^-1 + e^-1))
    a = np.array([0.0, 1.0])
    b = np.array([0.0, 1.0])
    expected = -math.log(math.exp(0) + 2 * math.exp(-1))
    got = soft_dtw_distance(a, b, gamma=1.0)
    assert got == pytest.approx(expected, abs=1e-9)
    # Known Soft-DTW property: it is NOT guaranteed non-negative (unlike hard DTW).
    assert expected < 0


def test_soft_dtw_gamma_fixed_at_one_by_default():
    from Code.common.metrics.temporal import SoftDTWScorer
    assert SoftDTWScorer.GAMMA == 1.0


# ---------------------------------------------------------------------------
# Wasserstein (EM14) - 1-D vs 2-D, the task 6d permutation demonstration
# ---------------------------------------------------------------------------

def test_wasserstein_1d_hand_computed():
    # Both already sorted; empirical 1-D Wasserstein between paired samples of equal
    # size with no ties = mean absolute difference of the sorted arrays.
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([4.0, 5.0, 6.0])
    assert wasserstein_1d(a, b) == pytest.approx(3.0)


def test_wasserstein_permutation_invariance_1d_vs_2d():
    """The task 6d demonstration: shuffling the forecast in time leaves the 1-D
    Wasserstein distance unchanged (it only sees the two VALUE multisets, {0,10} vs
    {0,10}: identical, distance 0) but changes the 2-D (time,value) distance, because
    reordering moves the points to different locations in the plane.
    """
    actual = np.array([0.0, 10.0])
    forecast_matched = np.array([0.0, 10.0])   # same order as actual
    forecast_shuffled = np.array([10.0, 0.0])  # same VALUES, reversed order

    # 1-D: identical value distributions regardless of order.
    assert wasserstein_1d(actual, forecast_matched) == pytest.approx(0.0)
    assert wasserstein_1d(actual, forecast_shuffled) == pytest.approx(0.0)

    # 2-D: hand-computed. Points: actual=(0,0),(1,10). forecast_matched=(0,0),(1,10)
    # -> identical points, cost 0.
    assert wasserstein_2d_time_value(actual, forecast_matched) == pytest.approx(0.0)

    # forecast_shuffled points: (0,10),(1,0). Two assignments:
    #   identity: (0-0)^2+(0-10)^2 + (1-1)^2+(10-0)^2 = 100 + 100 = 200 -> /n=2 -> 100
    #   swap:     (0-1)^2+(0-0)^2 + (1-0)^2+(10-10)^2 = 1 + 1 = 2       -> /n=2 -> 1
    # Hungarian assignment picks the cheaper (swap): 1.0.
    assert wasserstein_2d_time_value(actual, forecast_shuffled) == pytest.approx(1.0)
    # And crucially, unlike the 1-D case, this is NOT zero even though the value
    # multiset is identical - this is the whole point of the task 6d comparison.
    assert wasserstein_2d_time_value(actual, forecast_shuffled) != pytest.approx(
        wasserstein_1d(actual, forecast_shuffled)
    )


# ---------------------------------------------------------------------------
# TDI (EM15)
# ---------------------------------------------------------------------------

def test_tdi_identical_series_is_zero():
    a = np.array([1.0, 2.0, 3.0])
    assert tdi_distance(a, a.copy()) == 0.0


def test_tdi_constant_offset_is_zero_shape_only_metric():
    # Same pair as the DTW constant-offset test: a and b have IDENTICAL shape (just a
    # constant value offset), so the optimal DTW path is the pure diagonal (i==j for
    # every point) - hand-traced above. TDI only measures TEMPORAL displacement
    # (i-j), so a purely value-shifted pair (no timing distortion at all) must score 0,
    # even though DTW itself is 3.0 for this same pair - the two metrics measure
    # orthogonal things by design.
    a = np.array([0.0, 0.0, 0.0])
    b = np.array([1.0, 1.0, 1.0])
    assert tdi_distance(a, b) == 0.0


def test_tdi_nonzero_when_shape_is_time_shifted():
    # a has a single peak at index 2; b has the SAME peak shape shifted one step later
    # (index 3). Aligning the peaks forces the warping path off the diagonal at that
    # point (i=2 pairs with j=3, a displacement of 1), so TDI must be strictly positive.
    a = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    b = np.array([1.0, 1.0, 2.0, 3.0, 2.0])
    assert tdi_distance(a, b) > 0.0


# ---------------------------------------------------------------------------
# TDA (EM16) / DA (EM17)
# ---------------------------------------------------------------------------

def test_tda_and_da_hand_computed():
    origin = 0.0
    actual_h = np.array([1.0, 2.0, -1.0, -2.0])
    forecast_h = np.array([1.0, -1.0, -1.0, 2.0])

    # TDA: sign(x - origin) at each step.
    #   actual signs vs 0:   [+, +, -, -]
    #   forecast signs vs 0: [+, -, -, +]
    #   matches: idx0 Y, idx1 N, idx2 Y, idx3 N -> 2/4 = 0.5
    assert trend_direction_accuracy(origin, actual_h, forecast_h) == pytest.approx(0.5)

    # DA: sign(x[h]-x[h-1]), each series against its own previous value (h=1 vs origin).
    #   actual:   prev=[0,1,2,-1],   diff=[1,1,-3,-1]  -> signs [+,+,-,-]
    #   forecast: prev=[0,1,-1,-1],  diff=[1,-2,0,3]   -> signs [+,-,0,+]
    #   matches: idx0 (+,+) Y, idx1 (+,-) N, idx2 (-,0) N, idx3 (-,+) N -> 1/4 = 0.25
    assert directional_accuracy(origin, actual_h, forecast_h) == pytest.approx(0.25)


def test_da_tie_break_flat_vs_flat_is_a_match():
    # Documented tie-break default (task 6c): a flat (zero) actual change only counts
    # as correctly called if the forecast is ALSO exactly flat.
    origin = 5.0
    actual_h = np.array([5.0])     # no change from origin -> sign 0
    forecast_flat = np.array([5.0])   # sign 0 -> match
    forecast_up = np.array([6.0])     # sign + -> no match
    assert directional_accuracy(origin, actual_h, forecast_flat) == pytest.approx(1.0)
    assert directional_accuracy(origin, actual_h, forecast_up) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TPA (EM18)
# ---------------------------------------------------------------------------

def test_tpa_exact_turning_point_match():
    # actual_seq (origin at idx0): 0,1,2,1,0. Interior points checked at idx1,2,3.
    #   idx1 (0,1,2): 1>0 but 1<2 -> not an extremum.
    #   idx2 (1,2,1): 2>1 and 2>1 -> PEAK at idx2.
    #   idx3 (2,1,0): 1<2 but 1>0 -> not an extremum.
    # -> exactly one actual turning point, at index 2.
    actual_seq = np.array([0.0, 1.0, 2.0, 1.0, 0.0])
    forecast_exact = np.array([0.0, 1.0, 3.0, 1.0, 0.0])  # peak also at idx2
    tpa, had_tp = turning_point_accuracy(actual_seq, forecast_exact, tolerance=1)
    assert had_tp is True
    assert tpa == pytest.approx(1.0)


def test_tpa_within_tolerance_match():
    # Forecast's peak lands at idx3 instead of idx2 - a 1-step miss, within tolerance=1.
    actual_seq = np.array([0.0, 1.0, 2.0, 1.0, 0.0])
    forecast_shifted = np.array([0.0, 1.0, 2.0, 3.0, 0.0])  # peak at idx3
    tpa, had_tp = turning_point_accuracy(actual_seq, forecast_shifted, tolerance=1)
    assert had_tp is True
    assert tpa == pytest.approx(1.0)


def test_tpa_no_forecast_turning_point_scores_zero():
    actual_seq = np.array([0.0, 1.0, 2.0, 1.0, 0.0])
    forecast_monotonic = np.array([0.0, 1.0, 2.0, 3.0, 4.0])  # no turning point at all
    tpa, had_tp = turning_point_accuracy(actual_seq, forecast_monotonic, tolerance=1)
    assert had_tp is True
    assert tpa == pytest.approx(0.0)


def test_tpa_undefined_fallback_when_actual_has_no_turning_point():
    # task 6b's documented default: no actual turning points -> (0.5, False), a neutral
    # "no information" value rather than crashing model selection.
    actual_seq = np.array([0.0, 1.0, 2.0, 3.0, 4.0])  # strictly monotonic
    forecast_seq = np.array([0.0, 1.0, 2.0, 1.0, 0.0])
    tpa, had_tp = turning_point_accuracy(actual_seq, forecast_seq, tolerance=1)
    assert had_tp is False
    assert tpa == pytest.approx(0.5)
