"""Write one experiment's results to Results/Results_<tab_name>.xlsx (one sheet per
exp_id) plus a run_config.json under Results/RunConfigs/<tab_name>/<exp_id>.json.

Resume logic (P2-07): already_has_result() is checked by the tab runner BEFORE calling
run_single_experiment, so a re-run skips any exp_id that already has a sheet - a crash
partway through a tab must not cost the runs that already finished.
"""
from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pandas as pd
from openpyxl.utils.dataframe import dataframe_to_rows

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "Results"
RUN_CONFIG_DIR = RESULTS_DIR / "RunConfigs"


def already_has_result(workbook_path: Path, exp_id: str) -> bool:
    if not workbook_path.exists():
        return False
    try:
        wb = openpyxl.load_workbook(workbook_path, read_only=True)
        present = exp_id in wb.sheetnames
        wb.close()
        return present
    except Exception:
        # A workbook that fails to open (e.g. mid-write from a prior crash) is treated
        # as not having the result, so it gets regenerated rather than silently skipped.
        return False


def write_block_header(ws, row: int, text: str) -> int:
    ws.cell(row=row, column=1, value=text).font = openpyxl.styles.Font(bold=True)
    return row + 1


def write_dataframe_block(ws, start_row: int, df: pd.DataFrame) -> int:
    """Writes df starting at start_row (header row included). Returns the next free row."""
    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True)):
        for c_idx, value in enumerate(row, start=1):
            ws.cell(row=start_row + r_idx, column=c_idx, value=value)
    return start_row + len(df) + 2  # +1 header, +1 blank spacer


def write_result_sheet(
    tab_name: str,
    exp_id: str,
    metadata: dict,
    forecast_df: pd.DataFrame,
    weights_df: pd.DataFrame,
    posthoc_df: pd.DataFrame,
    release_labels: dict,
) -> Path:
    """metadata: flat dict of scalar experiment info (index, frequency, eval_metric,
    train_data_end, runtime_sec, gpu_name, ...). forecast_df: date, actual, mean, and
    one column per quantile level. weights_df: model, family, variant, release_date,
    weight - one row per model AutoGluon actually fitted (zero-weight models included,
    per task 7's "every constituent model"). posthoc_df: output of
    metrics.posthoc.compute_posthoc_table. release_labels: {"chronos_t5": "fully_pre"|
    "straddling"|"fully_post", "chronos_bolt": ..., "chronos_2": ...} for this origin.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    workbook_path = RESULTS_DIR / f"Results_{tab_name}.xlsx"

    if workbook_path.exists():
        wb = openpyxl.load_workbook(workbook_path)
        if exp_id in wb.sheetnames:
            del wb[exp_id]
    else:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # drop the default empty sheet

    ws = wb.create_sheet(title=exp_id)

    row = write_block_header(ws, 1, f"Experiment {exp_id}")
    meta_df = pd.DataFrame({"field": list(metadata.keys()), "value": list(metadata.values())})
    row = write_dataframe_block(ws, row, meta_df)

    row = write_block_header(ws, row, "Forecast (point + quantiles)")
    row = write_dataframe_block(ws, row, forecast_df)

    row = write_block_header(ws, row, "Ensemble weights (every fitted model; family = pretrained-foundation "
                                        "or trained-from-scratch; release_date set only for pretrained variants)")
    row = write_dataframe_block(ws, row, weights_df)

    row = write_block_header(
        ws, row,
        "Post-hoc metrics: EM2-EM18 on level / period_on_period / year_on_year "
        "(governs Phase 4 reporting; NOT what the ensemble was fitted to optimise)",
    )
    row = write_dataframe_block(ws, row, posthoc_df)

    row = write_block_header(
        ws, row,
        "Release-date origin labels (for the deferred contamination diff-in-diff analysis - "
        "see INDEX_SET_CHANGE.md; computed once here so Phase 4 doesn't have to redo it)",
    )
    labels_df = pd.DataFrame({"pretrained_variant": list(release_labels.keys()),
                               "origin_position_vs_release": list(release_labels.values())})
    write_dataframe_block(ws, row, labels_df)

    wb.save(workbook_path)
    return workbook_path


def write_run_config(tab_name: str, exp_id: str, config: dict) -> Path:
    out_dir = RUN_CONFIG_DIR / tab_name
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{exp_id}.json"
    path.write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")
    return path
