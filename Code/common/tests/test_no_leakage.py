"""P2-02: prove the rolling-origin cutoff is airtight - nothing after train_data_end
reaches training, validation, or scaling.

Two layers (see the approved plan, "Leakage proof"):
  1. Fast, deterministic, always-run: corrupt every value strictly after train_data_end
     to an absurd constant BEFORE calling the data-loading/slicing code, and assert the
     resulting TimeSeriesDataFrame handed to .fit() is byte-identical to the clean run's.
     This is the structural proof: our own slicing code - the classic place a "fit a
     scaler on the full series first" mistake would live - never lets a post-cutoff
     value survive into what AutoGluon sees.
  2. Slower, end-to-end smoke test: same corruption, but actually fit()/predict() with
     deterministic, non-GPU models (Naive, SeasonalNaive) and assert the forecasts
     themselves are byte-identical. Kept separate from (1) and marked slow because a
     full GPU-pool fit is not guaranteed bit-reproducible even with a fixed seed, so
     this only uses models with no such risk.

This file does not modify Data/final_data.csv - it reads it once and corrupts an
in-memory copy.
"""
from __future__ import annotations

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from Code.common.data import (
    FINAL_DATA_PATH,
    build_fixed_window_tsdf,
    build_train_tsdf,
    load_final_data,
    parse_plan_date,
)

ABSURD_VALUE = 1e12

# (index, frequency, train_data_end) - spans the shortest-history origin (first monthly,
# where leakage from just beyond the cutoff would be easiest to accidentally admit) and
# the last origin of each frequency, per the plan's origin table.
SAMPLE_ORIGINS = [
    ("HCPI", "monthly", "Dec 2019"),   # T05-M-001 / T01-M-001 - first monthly origin
    ("HCPI", "monthly", "Aug 2025"),   # last monthly origin (T*-M-069)
    ("HCPI", "quarterly", "Q4 2019"),  # first quarterly origin
    ("HCPI", "quarterly", "Q1 2026"),  # last quarterly origin
    ("HCPI", "annual", "2019"),        # first annual origin
    ("HCPI", "annual", "2024"),        # last annual origin
    ("FCPI", "monthly", "Dec 2019"),
    ("CCPI", "monthly", "Dec 2019"),
]


def _corrupted_copy(df: pd.DataFrame, train_data_end: pd.Timestamp) -> pd.DataFrame:
    corrupted = df.copy()
    mask = corrupted["date"] > train_data_end
    assert mask.any(), "test fixture error: no post-cutoff rows to corrupt"
    corrupted.loc[mask, "value"] = ABSURD_VALUE
    return corrupted


@pytest.mark.parametrize("index,frequency,train_data_end_str", SAMPLE_ORIGINS)
def test_slicing_is_immune_to_post_cutoff_corruption(index, frequency, train_data_end_str):
    train_data_end = parse_plan_date(train_data_end_str)
    clean = load_final_data(index, frequency)
    corrupted = _corrupted_copy(clean, train_data_end)

    clean_tsdf = build_train_tsdf(clean, train_data_end, item_id=index)
    corrupted_tsdf = build_train_tsdf(corrupted, train_data_end, item_id=index)

    assert_frame_equal(pd.DataFrame(clean_tsdf), pd.DataFrame(corrupted_tsdf))
    # Belt and braces: the absurd value must not appear anywhere in what we sliced out.
    assert not (pd.DataFrame(corrupted_tsdf)["target"] == ABSURD_VALUE).any()


@pytest.mark.slow
def test_end_to_end_forecast_is_immune_to_post_cutoff_corruption():
    """Full fit()/predict() with only deterministic, non-GPU models. Slower than the
    structural test above, so marked slow (run explicitly with `-m slow` or as part of
    the full suite, not on every quick pytest invocation)."""
    from autogluon.timeseries import TimeSeriesPredictor

    index, frequency, train_data_end_str = "HCPI", "monthly", "Dec 2019"
    train_data_end = parse_plan_date(train_data_end_str)
    clean = load_final_data(index, frequency)
    corrupted = _corrupted_copy(clean, train_data_end)

    def fit_and_predict(series: pd.DataFrame) -> pd.DataFrame:
        tsdf = build_train_tsdf(series, train_data_end, item_id=index)
        predictor = TimeSeriesPredictor(
            target="target", prediction_length=12, freq="MS", quantile_levels=[0.5],
            verbosity=0, eval_metric="MAE",
        ).fit(
            tsdf, hyperparameters={"Naive": {}, "SeasonalNaive": {}},
            time_limit=60, random_seed=123, enable_ensemble=False,
        )
        return pd.DataFrame(predictor.predict(tsdf))

    clean_forecast = fit_and_predict(clean)
    corrupted_forecast = fit_and_predict(corrupted)
    assert_frame_equal(clean_forecast, corrupted_forecast)


# ---------------------------------------------------------------------------
# Fixed rolling window (post-restructure): the leakage boundary is now on BOTH
# sides. Real T01-S1-M rows (train_window_periods=72, monthly HCPI Set 1),
# spanning first/middle/last origin.
# ---------------------------------------------------------------------------

FIXED_WINDOW_ORIGINS = [
    # (train_data_start, train_data_end, train_window_periods) - exp_id in comment
    ("Jan 2014", "Dec 2019", 72),  # T01-S1-M-001 / T05-S1-M-001
    ("Jul 2016", "Jun 2022", 72),  # T01-S1-M-031 (mid-sequence)
    ("Sep 2019", "Aug 2025", 72),  # T01-S1-M-069 (last origin)
]


@pytest.mark.parametrize("index", ["HCPI"])
@pytest.mark.parametrize("start_str,end_str,expected_periods", FIXED_WINDOW_ORIGINS)
def test_fixed_window_exact_row_count_and_bounds(index, start_str, end_str, expected_periods):
    """Task requirement: assert the data passed to fit() starts exactly at
    train_data_start, ends exactly at train_data_end, and is exactly train_window_periods
    rows. An off-by-one here silently changes every downstream result."""
    train_data_start = parse_plan_date(start_str)
    train_data_end = parse_plan_date(end_str)
    series = load_final_data(index, "monthly")

    tsdf = build_fixed_window_tsdf(series, train_data_start, train_data_end, item_id=index,
                                     expected_periods=expected_periods)
    df = pd.DataFrame(tsdf).reset_index()

    assert len(df) == expected_periods
    assert df["timestamp"].min() == pd.Timestamp(train_data_start)
    assert df["timestamp"].max() == pd.Timestamp(train_data_end)


@pytest.mark.parametrize("start_str,end_str,expected_periods", FIXED_WINDOW_ORIGINS)
def test_fixed_window_immune_to_corruption_after_end(start_str, end_str, expected_periods):
    """Post-cutoff corruption (the original leakage test's direction), re-proven against
    the fixed-window builder specifically."""
    index = "HCPI"
    train_data_start = parse_plan_date(start_str)
    train_data_end = parse_plan_date(end_str)
    clean = load_final_data(index, "monthly")

    corrupted = clean.copy()
    mask = corrupted["date"] > train_data_end
    assert mask.any(), "test fixture error: no post-cutoff rows to corrupt"
    corrupted.loc[mask, "value"] = ABSURD_VALUE

    clean_tsdf = build_fixed_window_tsdf(clean, train_data_start, train_data_end, index, expected_periods)
    corrupted_tsdf = build_fixed_window_tsdf(corrupted, train_data_start, train_data_end, index, expected_periods)

    assert_frame_equal(pd.DataFrame(clean_tsdf), pd.DataFrame(corrupted_tsdf))
    assert not (pd.DataFrame(corrupted_tsdf)["target"] == ABSURD_VALUE).any()


# Origin 1 (Jan 2014) is excluded here: its train_data_start coincides with the series'
# own first observation (HCPI data starts 2014-01), so there is structurally nothing
# before it to corrupt - not a leakage gap, just an origin where this boundary is
# vacuous. Covered instead by test_fixed_window_no_pre_window_data_exists_at_origin_1.
BEFORE_START_ORIGINS = [o for o in FIXED_WINDOW_ORIGINS if o[0] != "Jan 2014"]


def test_fixed_window_no_pre_window_data_exists_at_origin_1():
    """Documents WHY origin 1 is excluded from the before-start corruption test above,
    rather than silently dropping it: confirms there is genuinely no data before
    2014-01 for HCPI, so that boundary has nothing to test at this specific origin."""
    clean = load_final_data("HCPI", "monthly")
    assert (clean["date"] < parse_plan_date("Jan 2014")).sum() == 0


@pytest.mark.parametrize("start_str,end_str,expected_periods", BEFORE_START_ORIGINS)
def test_fixed_window_immune_to_corruption_before_start(start_str, end_str, expected_periods):
    """NEW half of the leakage proof: the fixed window must also be immune to
    corruption of everything BEFORE train_data_start. With the old expanding-window
    design, "everything before the cutoff" was legitimate training data by construction,
    so this direction did not exist as a leakage risk. It does now: a bug that slices
    only on the end date (e.g. reusing build_train_tsdf by mistake) would silently pull
    in pre-window history and would NOT be caught by the post-cutoff test above."""
    index = "HCPI"
    train_data_start = parse_plan_date(start_str)
    train_data_end = parse_plan_date(end_str)
    clean = load_final_data(index, "monthly")

    corrupted = clean.copy()
    mask = corrupted["date"] < train_data_start
    assert mask.any(), "test fixture error: no pre-window rows to corrupt"
    corrupted.loc[mask, "value"] = ABSURD_VALUE

    clean_tsdf = build_fixed_window_tsdf(clean, train_data_start, train_data_end, index, expected_periods)
    corrupted_tsdf = build_fixed_window_tsdf(corrupted, train_data_start, train_data_end, index, expected_periods)

    assert_frame_equal(pd.DataFrame(clean_tsdf), pd.DataFrame(corrupted_tsdf))
    assert not (pd.DataFrame(corrupted_tsdf)["target"] == ABSURD_VALUE).any()


def test_fixed_window_catches_a_real_off_by_one_bug():
    """Negative control: prove the test itself has teeth. A deliberately-wrong slice
    (using build_train_tsdf - the OLD expanding-window builder - against a fixed-window
    origin) must fail this equivalence, confirming the fixed-window test isn't vacuously
    passing regardless of what's fed to it."""
    index = "HCPI"
    train_data_start = parse_plan_date("Sep 2019")
    train_data_end = parse_plan_date("Aug 2025")
    clean = load_final_data(index, "monthly")

    correct = build_fixed_window_tsdf(clean, train_data_start, train_data_end, index, 72)
    wrong = build_train_tsdf(clean, train_data_end, index)  # expanding: series-start..end

    assert len(wrong) > len(correct), (
        "sanity check failed: the expanding-window builder should include MORE rows "
        "than the fixed 72-month window at this origin (series starts 2014-01, window "
        "starts 2019-09) - if this assertion fails, the two builders are behaving "
        "identically and the fixed-window tests above are not actually discriminating."
    )
