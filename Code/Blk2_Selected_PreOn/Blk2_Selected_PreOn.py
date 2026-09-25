"""Blk2_Selected_PreOn - Block 2.1, the revised origin extension.

3 indices (HCPI, FCPI, CCPI) x 3 fitting objectives per index x 11 monthly origins
(o53-o63, May 2024 - Mar 2025 horizon starts) = 99 runs. The fitting objectives were
selected SEPARATELY FOR EACH TARGET in Block 1.1, ranked on YoY accuracy
(Results/Blk11_OBJECTIVE_SELECTION.md section 10), so the objective differs by index:

    HCPI  EM12 (DTW), EM11 (MQL), EM13 (Soft-DTW)
    FCPI  EM11 (MQL), EM4 (MAPE), EM2 (MAE)
    CCPI  EM12 (DTW), EM13 (Soft-DTW), EM14 (Wasserstein)

It is read per-row from Code/experiments.csv (column eval_metric), exactly as in
Code/Blk11_MetricSearch/Blk11_MetricSearch.py, which this runner is adapted from - the
generated one-tab-one-metric template (generate_tab_runners.py) cannot serve six
objectives.

Row filter: block == "2.1" AND exp_id starts with "B21-". block == "2.1" alone also picks
up 36 BL-M-* baseline rows that belong to Blk5_Baselines; the tab's B22-*/B23-* rows sit
under blocks 2.2/2.3. validate_rows() asserts the exact 99-row design and each row's
124-month training window against Data/final_data.csv before anything is fitted.

Skips any exp_id that already has a result sheet (resume), writes one sheet per
experiment to Results/Results_Blk2_Selected_PreOn.xlsx plus a run_config.json per run
under Results/RunConfigs/Blk2_Selected_PreOn/, and rewrites Results/PROGRESS.md after
every run.

All real logic lives in Code/common/experiment.py's run_single_experiment(). Controls
(time_limit, random_seed) are read from Code/common/config_Blk2_Selected_PreOn.yaml; CLI
flags override.

Run: python Code/Blk2_Selected_PreOn/Blk2_Selected_PreOn.py [--exp-id <id>] [--index HCPI]
     [--force] [--time-limit 900] [--validate-only]
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from Code.common.data import FINAL_DATA_PATH, parse_plan_date  # noqa: E402
from Code.common.experiment import load_tab_controls, run_single_experiment  # noqa: E402
from Code.common.results_io import (  # noqa: E402
    RESULTS_DIR,
    RUN_CONFIG_DIR,
    already_has_result,
    write_result_sheet,
    write_run_config,
)

TAB_NAME = "Blk2_Selected_PreOn"
BLOCK = "2.1"
EXP_ID_PREFIX = "B21-"
EXPECTED_ROWS = 99
EXPECTED_OBJECTIVES = {
    "HCPI": {"EM12", "EM11", "EM13"},
    "FCPI": {"EM11", "EM4", "EM2"},
    "CCPI": {"EM12", "EM13", "EM14"},
}
EXPECTED_ORIGINS = set(range(53, 64))
TOTAL_WINDOW = 124
N_PERIODS = 12

EXPERIMENTS_CSV = REPO_ROOT / "Code" / "experiments.csv"
WORKBOOK_PATH = RESULTS_DIR / f"Results_{TAB_NAME}.xlsx"
RUN_CONFIG_TAB_DIR = RUN_CONFIG_DIR / TAB_NAME
PROGRESS_PATH = RESULTS_DIR / "PROGRESS.md"

SESSION_START = time.monotonic()


def load_block_rows() -> list[dict]:
    with open(EXPERIMENTS_CSV, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if r["block"] == BLOCK and r["exp_id"].startswith(EXP_ID_PREFIX)]
    if len(rows) != EXPECTED_ROWS:
        raise SystemExit(f"Expected exactly {EXPECTED_ROWS} rows for block {BLOCK!r} with exp_id "
                         f"prefix {EXP_ID_PREFIX!r}, got {len(rows)} - filter is wrong, stopping.")
    return rows


def validate_rows(rows: list[dict]) -> None:
    """Asserts the full 99-row design and every row's window against Data/final_data.csv.
    Raises SystemExit listing every failure - nothing is fitted if this fails.
    """
    errors = []
    ids = [r["exp_id"] for r in rows]
    if len(rows) != EXPECTED_ROWS:
        errors.append(f"{len(rows)} rows, expected {EXPECTED_ROWS}")
    if len(set(ids)) != len(ids):
        errors.append("duplicate exp_ids")
    bad_ids = [i for i in ids if i.startswith(("BL-", "B22-", "B23-")) or not i.startswith(EXP_ID_PREFIX)]
    if bad_ids:
        errors.append(f"out-of-scope exp_ids: {bad_ids}")

    per_index = Counter(r["index"] for r in rows)
    if set(per_index) != set(EXPECTED_OBJECTIVES) or any(n != 33 for n in per_index.values()):
        errors.append(f"rows per index {dict(per_index)}, expected 33 each of {sorted(EXPECTED_OBJECTIVES)}")
    for index, objectives in EXPECTED_OBJECTIVES.items():
        sub = [r for r in rows if r["index"] == index]
        found = {r["eval_metric"] for r in sub}
        if found != objectives:
            errors.append(f"{index}: objectives {sorted(found)}, expected {sorted(objectives)}")
        origins = {int(r["origin_no"]) for r in sub}
        if origins != EXPECTED_ORIGINS:
            errors.append(f"{index}: origins {sorted(origins)}, expected 53-63")
        for em in objectives:
            cell = [r for r in sub if r["eval_metric"] == em]
            cell_origins = sorted(int(r["origin_no"]) for r in cell)
            if cell_origins != sorted(EXPECTED_ORIGINS):
                errors.append(f"{index}/{em}: {len(cell)} rows, origins {cell_origins}, expected 11 (53-63)")

    data = pd.read_csv(FINAL_DATA_PATH, parse_dates=["date"])
    data = data[data["frequency"] == "monthly"]
    for r in rows:
        eid = r["exp_id"]
        if r["frequency"] != "Monthly" or int(r["n_periods"]) != N_PERIODS \
                or int(r["total_window"]) != TOTAL_WINDOW or int(r["train_periods"]) != 100 \
                or int(r["validation_periods"]) != 24 or r["pretrained_models"].strip() != "Yes":
            errors.append(f"{eid}: controls differ (frequency={r['frequency']}, n_periods={r['n_periods']}, "
                          f"train/val/total={r['train_periods']}/{r['validation_periods']}/{r['total_window']}, "
                          f"pretrained={r['pretrained_models']})")
        ts, te = parse_plan_date(r["train_data_start"]), parse_plan_date(r["train_data_end"])
        hs, he = parse_plan_date(r["horizon_start"]), parse_plan_date(r["horizon_end"])
        series = data[data["index"] == r["index"]].set_index("date")["value"].dropna()
        n_train = int(((series.index >= ts) & (series.index <= te)).sum())
        n_actual = int(((series.index >= hs) & (series.index <= he)).sum())
        if n_train != TOTAL_WINDOW:
            errors.append(f"{eid}: {n_train} monthly rows {ts:%b %Y}-{te:%b %Y}, expected {TOTAL_WINDOW}")
        if n_actual != N_PERIODS:
            errors.append(f"{eid}: {n_actual} actuals {hs:%b %Y}-{he:%b %Y}, expected {N_PERIODS}")
        if te + pd.DateOffset(months=1) != hs:
            errors.append(f"{eid}: train_data_end {te:%b %Y} is not the month before horizon_start {hs:%b %Y}")

    if errors:
        raise SystemExit("Row validation FAILED - nothing fitted:\n  " + "\n  ".join(errors))


def print_rows(rows: list[dict]) -> None:
    print(f"{'exp_id':<10} {'index':<5} {'obj':<5} {'o':>3}  {'train':<19} {'horizon':<19}")
    for r in rows:
        print(f"{r['exp_id']:<10} {r['index']:<5} {r['eval_metric']:<5} {r['origin_no']:>3}  "
              f"{r['train_data_start'] + '-' + r['train_data_end']:<19} "
              f"{r['horizon_start'] + '-' + r['horizon_end']:<19}")


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def write_progress(rows: list[dict]) -> None:
    # Count completed against the same (possibly --index/--exp-id filtered) row set being
    # run - counting every JSON in the directory against a filtered total is what made
    # Block 1.1 report "213 / 102" and "Projected finish: n/a".
    wanted = {r["exp_id"] for r in rows}
    total = len(wanted)
    records = []
    for exp_id in sorted(wanted):
        p = RUN_CONFIG_TAB_DIR / f"{exp_id}.json"
        if not p.exists():
            continue
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        records.append((exp_id, cfg.get("runtime_sec"), p.stat().st_mtime))

    completed = len(records)
    runtimes = [r for _, r, _ in records if r is not None]
    mean_rt = statistics.mean(runtimes) if runtimes else 0.0
    median_rt = statistics.median(runtimes) if runtimes else 0.0
    elapsed_sec = time.monotonic() - SESSION_START
    remaining = total - completed
    projected_finish = "done" if remaining == 0 else "n/a"
    if remaining and mean_rt:
        eta = datetime.now() + timedelta(seconds=remaining * mean_rt)
        projected_finish = eta.strftime("%Y-%m-%d %H:%M:%S")

    last5 = sorted(records, key=lambda r: r[2])[-5:]

    lines = [
        "# Block 2.1 - Revised origin extension (Blk2_Selected_PreOn) progress",
        "",
        f"- Block: {BLOCK} (exp_id {EXP_ID_PREFIX}*)",
        f"- Completed: {completed} / {total}",
        f"- Mean runtime: {mean_rt:.1f}s" if runtimes else "- Mean runtime: n/a",
        f"- Median runtime: {median_rt:.1f}s" if runtimes else "- Median runtime: n/a",
        f"- Elapsed (this session): {_fmt_duration(elapsed_sec)}",
        f"- Projected finish: {projected_finish}",
        "",
        "## Last 5 completed runs",
        "",
        "| exp_id | runtime_sec |",
        "|---|---|",
    ]
    for exp_id, rt, _mtime in reversed(last5):
        lines.append(f"| {exp_id} | {rt if rt is not None else 'n/a'} |")
    lines.append("")
    lines.append(f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")

    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text("\n".join(lines), encoding="utf-8")


def verify_run(result, row: dict) -> None:
    """Soft checks per CONTROLS - printed, not fatal, so one odd run doesn't abort the
    block.
    """
    md = result.metadata
    if md.get("eval_metric_code_fitted") != row["eval_metric"]:
        print(f"    WARNING: {result.exp_id} fitted {md.get('eval_metric_code_fitted')!r}, "
              f"row says {row['eval_metric']!r}")
    deployed = md.get("deployed_model")
    if deployed and deployed.endswith("_FULL"):
        print(f"    WARNING: {result.exp_id} deployed_model={deployed!r} - expected refit_full=False "
              "to never produce a _FULL ensemble.")
    if md.get("train_rows_actual") != TOTAL_WINDOW:
        print(f"    WARNING: {result.exp_id} train_rows_actual={md.get('train_rows_actual')}")
    fitted = result.run_config.get("model_pool_fitted", [])
    missing = [m for m in ("Chronos[small]", "Chronos[bolt_small]", "Chronos2") if m not in fitted]
    if missing:
        print(f"    WARNING: {result.exp_id} - Chronos variant(s) {missing} missing from the fitted "
              f"leaderboard (model_pool_fitted={fitted}). pretrained_models=Yes for this block.")


def main() -> None:
    controls = load_tab_controls(TAB_NAME)

    parser = argparse.ArgumentParser()
    parser.add_argument("--exp-id", default=None, help="run only this exp_id")
    parser.add_argument("--index", default=None, help='filter to one index, e.g. "HCPI"')
    parser.add_argument("--force", action="store_true", help="re-run even if a result already exists")
    parser.add_argument("--time-limit", type=int, default=controls["time_limit"])
    parser.add_argument("--num-val-windows", type=int, default=None,
                        help="override; default derives 2 per row from validation_periods/n_periods")
    parser.add_argument("--random-seed", type=int, default=controls["random_seed"])
    parser.add_argument("--validate-only", action="store_true",
                        help="print and validate the 99 rows, then exit without fitting")
    args = parser.parse_args()

    all_rows = load_block_rows()
    validate_rows(all_rows)
    if args.validate_only:
        print_rows(all_rows)
        print(f"\nValidation passed: {len(all_rows)} rows.")
        return

    rows = all_rows
    if args.index:
        rows = [r for r in rows if r["index"] == args.index]
    if args.exp_id:
        rows = [r for r in rows if r["exp_id"] == args.exp_id]
        if not rows:
            raise SystemExit(f"exp_id {args.exp_id!r} not found in block {BLOCK} (after --index filter)")

    total = len(rows)
    n_run, n_skipped = 0, 0
    for row in rows:
        eval_metric_code = row["eval_metric"]
        if not args.force and already_has_result(WORKBOOK_PATH, row["exp_id"]):
            n_skipped += 1
            print(f"  {row['exp_id']} ({row['index']}, {eval_metric_code}): skipped (already has results)")
            continue
        print(f"  {row['exp_id']} ({row['index']}, {eval_metric_code}, o{row['origin_no']}): running...",
              flush=True)
        result = run_single_experiment(
            row, eval_metric_code, time_limit=args.time_limit, num_val_windows=args.num_val_windows,
            random_seed=args.random_seed, refit_full=False,
        )
        write_result_sheet(
            TAB_NAME, result.exp_id, result.metadata, result.forecast_df,
            result.weights_df, result.posthoc_df, result.release_labels,
        )
        write_run_config(TAB_NAME, result.exp_id, result.run_config)
        verify_run(result, row)
        n_run += 1
        print(f"  {row['exp_id']}: done in {result.runtime_sec:.1f}s "
              f"(deployed_model={result.metadata.get('deployed_model')})", flush=True)
        write_progress(rows)

    print(f"\n{TAB_NAME}: {n_run} run, {n_skipped} skipped (of {total} total)")


if __name__ == "__main__":
    main()
