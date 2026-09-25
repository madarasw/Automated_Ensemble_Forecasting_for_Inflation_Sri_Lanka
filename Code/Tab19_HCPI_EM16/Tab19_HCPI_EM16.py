"""Tab19_HCPI_EM16 - Headline Consumer Price Index, EM16 (TDA) as the ensemble-fitting objective.

Reads Code/experiments.csv filtered to tab_name == "Tab19_HCPI_EM16", loops every row (train
through train_data_end, forecast the horizon), skips any exp_id that already has a
result sheet (resume - P2-07), writes one sheet per experiment to
Results/Results_Tab19_HCPI_EM16.xlsx plus a run_config.json per run.

GENERATED FILE - do not hand-edit. Regenerate with
Code/common/generate_tab_runners.py. All real logic lives in
Code/common/experiment.py's run_single_experiment(), which is the SAME function the
P2-01 single-experiment build uses - a tab is just that function looped over its own
rows. Controls (time_limit, num_val_windows, random_seed) are read from this tab's own
Code/common/config_Tab19_HCPI_EM16.yaml, not hardcoded here - CLI flags override the YAML.

Run: python Code/Tab19_HCPI_EM16/Tab19_HCPI_EM16.py [--exp-id <id>] [--set S1] [--frequency Monthly]
     [--force] [--time-limit 900]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from Code.common.experiment import load_tab_controls, run_single_experiment  # noqa: E402
from Code.common.results_io import RESULTS_DIR, already_has_result, write_result_sheet, write_run_config  # noqa: E402

TAB_NAME = "Tab19_HCPI_EM16"
EVAL_METRIC_CODE = "EM16"
EXPERIMENTS_CSV = REPO_ROOT / "Code" / "experiments.csv"


def load_tab_rows(set_filter: str | None = None, frequency_filter: str | None = None) -> list[dict]:
    with open(EXPERIMENTS_CSV, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["tab_name"] == TAB_NAME]
    if not rows:
        raise RuntimeError(f"No rows for {TAB_NAME} in {EXPERIMENTS_CSV}.")
    # Tabs 1-3 now span multiple sets/frequencies each (the Set 1/2/3 restructure) - a
    # tab is no longer automatically one index x one frequency x one set. Tabs 5-21
    # only ever have one set/frequency, so these filters are no-ops for them.
    if set_filter:
        rows = [r for r in rows if r.get("set") == set_filter]
    if frequency_filter:
        rows = [r for r in rows if r["frequency"] == frequency_filter]
    return rows


def main() -> None:
    controls = load_tab_controls(TAB_NAME)

    parser = argparse.ArgumentParser()
    parser.add_argument("--exp-id", default=None, help="run only this exp_id")
    parser.add_argument("--set", default=None, help='filter to one set, e.g. "S1" (Tabs 1-3 only)')
    parser.add_argument("--frequency", default=None, help='filter to one frequency, e.g. "Monthly"')
    parser.add_argument("--force", action="store_true", help="re-run even if a result already exists")
    parser.add_argument("--time-limit", type=int, default=controls["time_limit"])
    parser.add_argument("--num-val-windows", type=int, default=None,
                        help="override; default derives 2 per row from validation_periods/n_periods")
    parser.add_argument("--random-seed", type=int, default=controls["random_seed"])
    args = parser.parse_args()

    rows = load_tab_rows(set_filter=args.set, frequency_filter=args.frequency)
    if args.exp_id:
        rows = [r for r in rows if r["exp_id"] == args.exp_id]
        if not rows:
            raise SystemExit(f"exp_id {args.exp_id!r} not found in {TAB_NAME} (after --set/--frequency filters)")

    workbook_path = RESULTS_DIR / f"Results_{TAB_NAME}.xlsx"
    n_run, n_skipped = 0, 0
    for row in rows:
        if not args.force and already_has_result(workbook_path, row["exp_id"]):
            n_skipped += 1
            print(f"  {row['exp_id']}: skipped (already has results)")
            continue
        print(f"  {row['exp_id']}: running...")
        result = run_single_experiment(
            row, EVAL_METRIC_CODE, time_limit=args.time_limit, num_val_windows=args.num_val_windows,
            random_seed=args.random_seed,
        )
        write_result_sheet(
            TAB_NAME, result.exp_id, result.metadata, result.forecast_df,
            result.weights_df, result.posthoc_df, result.release_labels,
        )
        write_run_config(TAB_NAME, result.exp_id, result.run_config)
        n_run += 1
        print(f"  {row['exp_id']}: done in {result.runtime_sec:.1f}s")

    print(f"\n{TAB_NAME}: {n_run} run, {n_skipped} skipped (of {len(rows)} total)")


if __name__ == "__main__":
    main()
