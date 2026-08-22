"""Regenerate Code/experiments.csv and the 21 tab YAMLs from Main_Experiment_Plan.xlsx.

Run this after ANY edit to the plan workbook. The notebooks read the CSV and the
YAMLs - never the .xlsx - so a plan change is only live once this has been run.
"""
import csv, os, openpyxl

PLAN = "Main_Experiment_Plan.xlsx"
OUT_CSV = "out/Code/experiments.csv"
OUT_CFG = "out/Code/common"

wb = openpyxl.load_workbook(PLAN, data_only=True)
ws = wb["MASTER"]
hdr = [c.value for c in ws[4]]
rows = [dict(zip(hdr, [c.value for c in r])) for r in ws.iter_rows(min_row=5)]

os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
os.makedirs(OUT_CFG, exist_ok=True)

with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=hdr)
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if v is None else v) for k, v in r.items()})
print(f"{OUT_CSV}: {len(rows)} rows")

# ---- controls: read the CONTROLS sheet so the YAMLs carry the same blanks ----
cs = wb["CONTROLS"]
controls = []
for r in cs.iter_rows(min_row=5, max_col=2, values_only=True):
    if r[0]:
        controls.append((r[0], r[1] or ""))

KEY = {
    "Forecasting framework": "framework",
    "Framework version": "framework_version",
    "Preset / model pool": "preset_model_pool",
    "time_limit per fit (seconds)": "time_limit_s",
    "num_val_windows": "num_val_windows",
    "Quantile levels": "quantile_levels",
    "Target transformation": "target_transformation",
    "Random seed": "random_seed",
    "Training window": "training_window",
    "Data source and vintage": "data_source_and_vintage",
    "Series start date": "series_start_date",
    "Hardware": "hardware",
}

tabs = {}
for r in rows:
    tabs.setdefault(r["tab_name"], []).append(r)

for sheet, sub in sorted(tabs.items()):
    a = sub[0]
    freqs = sorted({x["frequency"] for x in sub})
    stage_label = ('Stage 3 - run after the metric is chosen'
                   if int(a['tab'].split()[1]) <= 4 else 'Stage 1 - run first')
    path = f"{OUT_CFG}/config_{sheet}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"""# Configuration for {sheet}
#
# Everything in this file is CONSTANT across all {len(sub)} experiments in this tab.
# The only thing that varies between experiments is the forecast origin, which comes
# from Code/experiments.csv (filter: tab_name == "{sheet}").
#
# The values under `controls:` MUST be identical in all 21 tab configs. The Stage 1
# comparison only works if the evaluation metric is the sole difference between tabs -
# if one tab runs with a different time limit or seed, the weight difference gets
# blamed on the metric when it was really the setting.

tab: "{a['tab']}"
tab_name: "{sheet}"
stage: "{stage_label}"

target:
  index: "{a['index']}"
  index_name: "{a['index_name']}"
  frequencies: [{", ".join(f'"{x}"' for x in freqs)}]

evaluation:
  metric_code: "{a['eval_metric']}"
  metric_name: "{a['metric_name']}"
  metric_family: "{a['metric_family']}"
  # This metric is the ENSEMBLE-FITTING OBJECTIVE. Every other metric is still
  # computed afterwards for reporting.

records:
  point_forecasts: true
  quantile_forecasts: {str('quantile' in a['records'].lower()).lower()}
  weight_distribution: true
  execution_time: true

experiments:
  source: "Code/experiments.csv"
  filter: 'tab_name == "{sheet}"'
  count: {len(sub)}
  # Each row supplies: exp_id, frequency, horizon_start, horizon_end, n_periods,
  # train_data_end. Train on data from series start THROUGH train_data_end inclusive.

output:
  workbook: "{a['result_workbook']}"
  sheet_per_experiment: true      # sheet name = exp_id
  run_config_json: true           # write resolved settings beside each result

runtime:
  resume: true                    # skip any exp_id that already has results -
                                  # a Colab disconnect must not cost the whole tab

controls:
""")
        for label, val in controls:
            k = KEY.get(label)
            if not k:
                continue
            v = str(val).strip()
            if v == "":
                f.write(f'  {k}: ""            # TO BE FILLED - see CONTROLS sheet\n')
            else:
                f.write(f'  {k}: "{v}"\n')
    print(f"  {path}")
