"""Smoke tests for the post-hoc metric table (level / period-on-period / year-on-year).
Not hand-worked exact-value tests (that's test_metrics_handworked.py for the underlying
formulas) - these check the plumbing: right shape, right EM codes present, and that a
PERFECT forecast scores as (near-)zero error / perfect direction everywhere it should.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from Code.common.metrics.posthoc import (
    NATIVE_EM,
    CUSTOM_EM,
    QUANTILE_EM,
    REPRESENTATIONS,
    PosthocInput,
    compute_posthoc_table,
)


def _synthetic_input(perfect: bool) -> PosthocInput:
    # A trend plus a slow wiggle (period 20 months, not a divisor of the 12-month
    # seasonal lag) so the YoY-transformed path actually has turning points within the
    # horizon - a pure straight-line level (no wiggle) produces a monotonic YoY path
    # with NO turning point, which correctly - not a bug - makes TPA (EM18) undefined
    # regardless of forecast quality (see METRIC_RULINGS.md 6b's documented fallback).
    t_past = np.arange(72)
    past_values = 100.0 + t_past * 0.5 + 3.0 * np.sin(2 * np.pi * t_past / 20)
    t_h = np.arange(72, 84)
    actual_h = 100.0 + t_h * 0.5 + 3.0 * np.sin(2 * np.pi * t_h / 20)
    forecast_h = actual_h.copy() if perfect else actual_h + 5.0  # a lousy, constant-bias forecast
    return PosthocInput(
        past_dates=pd.date_range("2014-01-01", periods=72, freq="MS"), past_values=past_values,
        horizon_dates=pd.date_range("2020-01-01", periods=12, freq="MS"), actual_h=actual_h, forecast_h=forecast_h,
        seasonal_period=12, quantiles_h=None,
    )


def test_table_shape_and_codes():
    table = compute_posthoc_table(_synthetic_input(perfect=False))
    assert set(table["representation"]) == set(REPRESENTATIONS)
    assert set(table["em_code"]) == set(NATIVE_EM) | set(CUSTOM_EM)
    assert len(table) == len(REPRESENTATIONS) * (len(NATIVE_EM) + len(CUSTOM_EM))


def test_quantile_metrics_are_none_without_quantile_forecasts():
    table = compute_posthoc_table(_synthetic_input(perfect=False))
    quantile_rows = table[table["em_code"].isin(QUANTILE_EM)]
    assert quantile_rows["value"].isna().all()


def test_perfect_forecast_scores_near_zero_error_on_level():
    table = compute_posthoc_table(_synthetic_input(perfect=True))
    level = table[table["representation"] == "level"].set_index("em_code")["value"]
    for code in ["EM2", "EM3", "EM4", "EM5", "EM6", "EM7", "EM8"]:  # MAE..WAPE point metrics
        assert level[code] == pytest.approx(0.0, abs=1e-6), f"{code} should be ~0 for a perfect forecast"
        assert level[code] >= 0, f"{code} is a loss metric and must report non-negative (sign convention check)"
    for code in ["EM12", "EM14", "EM15"]:  # DTW/Wasserstein/TDI: exactly 0 at identity
        assert level[code] == pytest.approx(0.0, abs=1e-6), f"{code} should be ~0 for a perfect forecast"
    # Soft-DTW (EM13) is a documented exception: it is NOT guaranteed to be 0 at identity
    # (log-sum-exp softmin bias - see the hand-worked test in test_metrics_handworked.py),
    # so the correct invariant here is "identity scores at least as well as a worse
    # forecast", not "== 0".
    for code in ["EM16", "EM17", "EM18"]:  # TDA/DA/TPA, stored as 1-accuracy (loss form)
        assert level[code] == pytest.approx(0.0, abs=1e-6), f"{code} should be ~0 (perfect direction) for a perfect forecast"


def test_biased_forecast_scores_worse_than_perfect_forecast():
    perfect_table = compute_posthoc_table(_synthetic_input(perfect=True))
    biased_table = compute_posthoc_table(_synthetic_input(perfect=False))
    for code in ["EM2", "EM3", "EM8", "EM13"]:  # MAE, RMSE, WAPE, Soft-DTW
        p = perfect_table[(perfect_table.em_code == code) & (perfect_table.representation == "level")]["value"].iloc[0]
        b = biased_table[(biased_table.em_code == code) & (biased_table.representation == "level")]["value"].iloc[0]
        assert b > p, f"{code}: biased forecast ({b}) should score worse than perfect ({p})"
