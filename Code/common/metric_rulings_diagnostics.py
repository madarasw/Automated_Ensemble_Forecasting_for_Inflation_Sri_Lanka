"""Real-data diagnostics for Data/METRIC_RULINGS.md (task 6). Computes what's knowable
from the ACTUAL data alone, before any pilot forecast exists: how many of the 69
monthly HCPI origins have zero actual turning points (6b), how often the actual YoY
series is exactly flat - the tie-relevant base rate (6c), and which origins' horizons
straddle the actual YoY zero-crossing (6a). The Wasserstein 1-D vs 2-D demonstration
(6d) doesn't need real data - see Code/common/tests/test_metrics_handworked.py's
test_wasserstein_permutation_invariance_1d_vs_2d.

This does NOT need AutoGluon, GPU, or any forecast - it is a property of the published
data and the dating rule alone. Run any time; re-run is cheap.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from Code.common.data import load_final_data, parse_plan_date  # noqa: E402
from Code.common.metrics.directional import _turning_points  # noqa: E402

MONTHLY_ORIGINS_START = pd.Timestamp("2020-01-01")
N_MONTHLY_ORIGINS = 69
SEASONAL_PERIOD = 12


def _yoy_series(values: np.ndarray) -> np.ndarray:
    out = np.full(len(values), np.nan)
    out[SEASONAL_PERIOD:] = (values[SEASONAL_PERIOD:] / values[:-SEASONAL_PERIOD] - 1.0) * 100.0
    return out


def analyse(index: str = "HCPI") -> pd.DataFrame:
    series = load_final_data(index, "monthly")
    dates = series["date"].to_numpy()
    values = series["value"].to_numpy()
    yoy = _yoy_series(values)
    yoy_by_date = dict(zip(pd.DatetimeIndex(dates), yoy))

    rows = []
    for i in range(N_MONTHLY_ORIGINS):
        horizon_start = MONTHLY_ORIGINS_START + pd.DateOffset(months=i)
        origin_date = horizon_start - pd.DateOffset(months=1)
        horizon_dates = [horizon_start + pd.DateOffset(months=h) for h in range(12)]

        origin_yoy = yoy_by_date.get(origin_date)
        horizon_yoy = [yoy_by_date.get(d) for d in horizon_dates]
        if origin_yoy is None or any(v is None or np.isnan(v) for v in ([origin_yoy] + horizon_yoy)):
            rows.append({"origin_index": i + 1, "horizon_start": horizon_start.date(), "status": "no actuals yet"})
            continue

        seq = np.array([origin_yoy] + horizon_yoy)
        tps = _turning_points(seq)
        step_diffs = np.diff(seq)
        n_flat_steps = int(np.sum(step_diffs == 0))
        crosses_zero = bool(np.any(np.diff(np.sign(seq)) != 0))

        rows.append({
            "origin_index": i + 1,
            "horizon_start": horizon_start.date(),
            "status": "ok",
            "n_turning_points": len(tps),
            "has_turning_point": len(tps) > 0,
            "n_flat_steps_of_12": n_flat_steps,
            "crosses_zero_in_horizon": crosses_zero,
        })
    return pd.DataFrame(rows)


def main() -> None:
    for index in ["HCPI", "FCPI", "CCPI"]:
        df = analyse(index)
        ok = df[df["status"] == "ok"]
        print(f"=== {index} monthly, {len(ok)}/{len(df)} origins with complete actuals ===")
        n_no_tp = int((~ok["has_turning_point"]).sum())
        print(f"  Origins with ZERO actual turning points (TPA undefined, task 6b): {n_no_tp}/{len(ok)}")
        print(f"    at origins: {ok.loc[~ok['has_turning_point'], 'horizon_start'].tolist()}")
        total_flat = int(ok["n_flat_steps_of_12"].sum())
        print(f"  Flat (zero-change) step-to-step YoY moves, out of {len(ok) * 12} total steps "
              f"(DA/TDA tie base rate, task 6c): {total_flat}")
        n_cross = int(ok["crosses_zero_in_horizon"].sum())
        print(f"  Origins whose horizon crosses YoY=0 (MAPE-on-YoY blow-up risk, task 6a): {n_cross}/{len(ok)}")
        print(f"    at origins: {ok.loc[ok['crosses_zero_in_horizon'], 'horizon_start'].tolist()}")
        print()


if __name__ == "__main__":
    main()
