"""Baseline forecasts: naive (random walk), random walk with drift, Atkeson-Ohanian,
seasonal-naive and ARIMA. No AutoGluon, no GPU - these fit in seconds, which is the
point of a baseline tab.

Why the naive/RW family was added (2026-09-25). The original set was seasonal-naive +
ARIMA only, and the ARIMA grid explicitly EXCLUDES p=q=0, so ARIMA(0,1,0) - a plain
random walk - was never a candidate, only a convergence fallback. A plain random walk
is the benchmark the inflation-forecasting literature treats as the bar to clear
(Atkeson & Ohanian 1999; see also the emerging-market evidence surveyed in
"As good as a random walk", CEPR). On a 17-origin check of this study's own data it was
by far the strongest of the simple benchmarks - mean absolute YoY error 1.76pp against
seasonal-naive's 2.29pp - and it beat the fitted ensembles on two of three targets.
Comparing only against seasonal-naive would therefore have overstated model skill.
"""
from __future__ import annotations

import time
import warnings

import numpy as np
from statsmodels.tsa.arima.model import ARIMA


def seasonal_naive_forecast(past_values: np.ndarray, prediction_length: int, seasonal_period: int) -> np.ndarray:
    """forecast[h] = the value exactly `seasonal_period` periods before horizon step h.
    Requires prediction_length <= seasonal_period - true for every tab in this plan, so
    every lag falls inside past_values. Degenerates to repeat-last-value (Naive) at
    annual frequency (seasonal_period=1).
    """
    if seasonal_period <= 1:
        return np.full(prediction_length, past_values[-1], dtype=float)
    if prediction_length > seasonal_period:
        raise NotImplementedError("prediction_length > seasonal_period not needed by this plan")
    return past_values[-seasonal_period:][:prediction_length].astype(float)


def _best_arima_order(y: np.ndarray, max_p: int = 2, max_d: int = 1, max_q: int = 2):
    best_aic, best_order, best_fit = np.inf, None, None
    for p in range(max_p + 1):
        for d in range(max_d + 1):
            for q in range(max_q + 1):
                if p == 0 and q == 0:
                    continue
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        fit = ARIMA(y, order=(p, d, q)).fit()
                    if fit.aic < best_aic:
                        best_aic, best_order, best_fit = fit.aic, (p, d, q), fit
                except Exception:
                    continue
    return best_order, best_fit


def arima_forecast(past_values: np.ndarray, prediction_length: int) -> tuple[np.ndarray, tuple | None]:
    """Grid search over ARIMA(p,d,q), p,d,q in {0,1,2} (excluding p=q=0), selected by
    AIC - a documented, minimal-dependency stand-in for pmdarima.auto_arima
    (statsmodels is already an autogluon.timeseries transitive dependency; nothing new
    added just for this baseline). Falls back to ARIMA(0,1,0) - a random walk - if
    every candidate order fails to converge (can happen on a very short series).
    """
    order, fit = _best_arima_order(past_values)
    if fit is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = ARIMA(past_values, order=(0, 1, 0)).fit()
        order = (0, 1, 0)
    forecast = np.asarray(fit.forecast(steps=prediction_length), dtype=float)
    return forecast, order


def naive_forecast(past_values: np.ndarray, prediction_length: int) -> np.ndarray:
    """Random walk: forecast[h] = the last observed value, for every h.

    The canonical no-change benchmark. On a persistent series such as a price index this
    is a hard bar to clear over a 12-month horizon, which is precisely why it is the
    standard comparator.
    """
    return np.full(prediction_length, float(past_values[-1]), dtype=float)


def drift_forecast(past_values: np.ndarray, prediction_length: int, seasonal_period: int) -> np.ndarray:
    """Random walk with drift: forecast[h] = last value + h * slope.

    `slope` is the average per-period change over the most recent `seasonal_period`
    periods (a trailing one-year drift), NOT the full-sample (y_T - y_1)/(T-1) slope.
    The trailing form is used because this study's windows are short (72 periods in the
    short-window block) and a full-sample slope would be dominated by history far
    outside the forecast's regime. Documented here because the two conventions give
    different numbers and the choice must be reproducible.
    """
    lag = max(int(seasonal_period), 1)
    if len(past_values) < lag + 1:
        raise ValueError(f"drift needs at least {lag + 1} past periods, got {len(past_values)}.")
    last = float(past_values[-1])
    slope = (last - float(past_values[-1 - lag])) / lag
    return last + slope * np.arange(1, prediction_length + 1, dtype=float)


def atkeson_ohanian_forecast(
    past_values: np.ndarray, prediction_length: int, seasonal_period: int
) -> np.ndarray:
    """Atkeson-Ohanian: the next `seasonal_period` periods' inflation equals the last
    `seasonal_period` periods' inflation.

    In index terms, forecast[h] = value[h - seasonal_period] * (1 + r), where r is the
    rate of change over the trailing `seasonal_period` periods. Equivalently:
    seasonal-naive scaled up by the latest year-on-year rate.

    Reference: Atkeson, A., & Ohanian, L. E. (2001), "Are Phillips Curves Useful for
    Forecasting Inflation?", Federal Reserve Bank of Minneapolis Quarterly Review,
    25(1), 2-11.

    Requires 2 * seasonal_period past periods (one full extra year behind the lag
    window) - the same requirement the YoY scorers' origin anchor has.
    """
    lag = max(int(seasonal_period), 1)
    if lag <= 1:
        return naive_forecast(past_values, prediction_length)
    if prediction_length > lag:
        raise NotImplementedError("prediction_length > seasonal_period not needed by this plan")
    if len(past_values) < 2 * lag:
        raise ValueError(
            f"Atkeson-Ohanian needs at least {2 * lag} past periods, got {len(past_values)}."
        )
    rate = float(past_values[-1]) / float(past_values[-1 - lag]) - 1.0
    base = np.asarray(past_values[-lag:][:prediction_length], dtype=float)
    return base * (1.0 + rate)


def run_baselines(past_values: np.ndarray, prediction_length: int, seasonal_period: int) -> dict:
    t0 = time.monotonic()
    nv_forecast = naive_forecast(past_values, prediction_length)
    nv_runtime = time.monotonic() - t0

    t0 = time.monotonic()
    dr_forecast = drift_forecast(past_values, prediction_length, seasonal_period)
    dr_runtime = time.monotonic() - t0

    t0 = time.monotonic()
    ao_forecast = atkeson_ohanian_forecast(past_values, prediction_length, seasonal_period)
    ao_runtime = time.monotonic() - t0

    t0 = time.monotonic()
    sn_forecast = seasonal_naive_forecast(past_values, prediction_length, seasonal_period)
    sn_runtime = time.monotonic() - t0

    t0 = time.monotonic()
    ar_forecast, ar_order = arima_forecast(past_values, prediction_length)
    ar_runtime = time.monotonic() - t0

    return {
        "naive_forecast": nv_forecast,
        "naive_runtime_sec": nv_runtime,
        "drift_forecast": dr_forecast,
        "drift_runtime_sec": dr_runtime,
        "atkeson_ohanian_forecast": ao_forecast,
        "atkeson_ohanian_runtime_sec": ao_runtime,
        "seasonal_naive_forecast": sn_forecast,
        "seasonal_naive_runtime_sec": sn_runtime,
        "arima_forecast": ar_forecast,
        "arima_order": ar_order,
        "arima_runtime_sec": ar_runtime,
    }
