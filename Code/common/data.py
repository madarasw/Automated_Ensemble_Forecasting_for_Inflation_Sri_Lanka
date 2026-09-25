"""Load Data/final_data.csv and build AutoGluon TimeSeriesDataFrames for one experiment.

This is the ONLY place that turns a plan row's dates into a train/score split. Every
experiment script goes through here so there's exactly one implementation of "train
through train_data_end inclusive, forecast the horizon" to get right (and to leakage-test).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from autogluon.timeseries import TimeSeriesDataFrame

REPO_ROOT = Path(__file__).resolve().parents[2]
FINAL_DATA_PATH = REPO_ROOT / "Data" / "final_data.csv"

_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_plan_date(s: str) -> pd.Timestamp:
    """Parse the plan's three date spellings into a period-start Timestamp.

    - Monthly:   "Dec 2019"  -> 2019-12-01
    - Quarterly: "Q4 2019"   -> 2019-10-01
    - Annual:    "2019"      -> 2019-01-01
    """
    s = s.strip()
    m = re.match(r"^([A-Za-z]{3})\s+(\d{4})$", s)
    if m:
        mon, year = m.group(1).lower(), int(m.group(2))
        if mon not in _MONTH_ABBR:
            raise ValueError(f"Unrecognised month abbreviation in plan date {s!r}")
        return pd.Timestamp(year=year, month=_MONTH_ABBR[mon], day=1)

    m = re.match(r"^Q([1-4])\s+(\d{4})$", s)
    if m:
        q, year = int(m.group(1)), int(m.group(2))
        return pd.Timestamp(year=year, month=(q - 1) * 3 + 1, day=1)

    m = re.match(r"^(\d{4})$", s)
    if m:
        return pd.Timestamp(year=int(m.group(1)), month=1, day=1)

    raise ValueError(f"Unrecognised plan date format: {s!r}")


FREQ_ALIAS = {"Monthly": "monthly", "Quarterly": "quarterly", "Annual": "annual"}
FREQ_TO_PANDAS = {"monthly": "MS", "quarterly": "QS", "annual": "YS"}
FREQ_TO_SEASONAL_PERIOD = {"monthly": 12, "quarterly": 4, "annual": 1}


def load_final_data(index: str, frequency: str, path: Path = FINAL_DATA_PATH) -> pd.DataFrame:
    """Read Data/final_data.csv, filter to one index/frequency, return tidy (date,value)
    sorted ascending. `frequency` accepts either the plan's "Monthly" or final_data's
    "monthly" spelling.
    """
    freq = FREQ_ALIAS.get(frequency, frequency)
    df = pd.read_csv(path, parse_dates=["date"])
    sub = df[(df["index"] == index) & (df["frequency"] == freq)].copy()
    if sub.empty:
        raise ValueError(f"No rows in {path} for index={index!r} frequency={freq!r}")
    sub = sub.sort_values("date").reset_index(drop=True)
    return sub[["date", "value"]]


def build_train_tsdf(series: pd.DataFrame, train_data_end: pd.Timestamp, item_id: str) -> TimeSeriesDataFrame:
    """EXPANDING window: slice `series` (date,value) to <= train_data_end. This is the
    leakage boundary for the (now superseded, Tab05-pilot-era) expanding-window design:
    nothing after train_data_end may appear in the returned object. Kept for the
    already-completed Tab 5 pilot; new experiments use build_fixed_window_tsdf below.
    """
    train = series[series["date"] <= train_data_end].copy()
    if train.empty:
        raise ValueError(f"No training data at or before {train_data_end}")
    train["item_id"] = item_id
    train = train.rename(columns={"date": "timestamp", "value": "target"})
    return TimeSeriesDataFrame.from_data_frame(train[["item_id", "timestamp", "target"]])


def build_fixed_window_tsdf(
    series: pd.DataFrame, train_data_start: pd.Timestamp, train_data_end: pd.Timestamp,
    item_id: str, expected_periods: int | None = None,
) -> TimeSeriesDataFrame:
    """FIXED ROLLING window: slice `series` to [train_data_start, train_data_end]
    inclusive on BOTH ends. This is the leakage boundary in both directions: nothing
    after train_data_end and nothing before train_data_start may appear in the returned
    object - the second half is new versus the old expanding-window design, where
    "everything before the cutoff" was legitimate by construction.

    If `expected_periods` is given (train_window_periods from the plan row), asserts the
    resulting window has exactly that many rows - an off-by-one here silently changes
    every downstream result, so this is checked eagerly rather than discovered later.
    """
    window = series[(series["date"] >= train_data_start) & (series["date"] <= train_data_end)].copy()
    if window.empty:
        raise ValueError(f"No training data in [{train_data_start.date()}, {train_data_end.date()}]")
    if expected_periods is not None and len(window) != expected_periods:
        raise ValueError(
            f"Fixed window [{train_data_start.date()}, {train_data_end.date()}] produced "
            f"{len(window)} rows, expected exactly {expected_periods} (train_window_periods). "
            "This usually means a gap in the source data or an off-by-one in the plan dates."
        )
    window["item_id"] = item_id
    window = window.rename(columns={"date": "timestamp", "value": "target"})
    return TimeSeriesDataFrame.from_data_frame(window[["item_id", "timestamp", "target"]])


def build_scoring_tsdf(
    series: pd.DataFrame, train_data_end: pd.Timestamp, horizon_end: pd.Timestamp, item_id: str
) -> TimeSeriesDataFrame:
    """Full series from series-start through horizon_end (train + actuals to score
    against), for use with TimeSeriesScorer.__call__ / predictor.evaluate(), which split
    off the trailing prediction_length rows as data_future themselves.
    """
    full = series[series["date"] <= horizon_end].copy()
    if full["date"].max() < horizon_end:
        raise ValueError(
            f"Actuals do not reach horizon_end={horizon_end.date()} "
            f"(last available: {full['date'].max().date()}) - cannot score this origin yet."
        )
    full["item_id"] = item_id
    full = full.rename(columns={"date": "timestamp", "value": "target"})
    return TimeSeriesDataFrame.from_data_frame(full[["item_id", "timestamp", "target"]])
