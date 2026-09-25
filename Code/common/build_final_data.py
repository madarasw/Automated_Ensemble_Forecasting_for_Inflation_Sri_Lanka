"""Build Data/final_data.csv - one tidy file holding every forecast target at monthly,
quarterly and annual frequency.

Targets (index codes follow Sri Lankan convention, NOT the abstract's original codes):

  HCPI  Headline / all-items CPI = the DCS National CPI (NCPI). Main variable.
  FCPI  NCPI food group, same publication.
  CCPI  Colombo CPI, all items - a SECOND headline target, not a core measure.

  All three are DCS series, 2013=100 and 2021=100 vintages chain-linked onto the 2021 base
  at Jan 2022, so all three are on one base and cover exactly 2014-01 .. 2026-08.

  ECPI is dropped. No source publishes a Sri Lankan energy CPI; the nearest DCS sub-group
  ("Housing, Water, Electricity, Gas and Other Fuels", 18% weight) is mostly housing and
  ends Dec 2022.

Why the old HCPI series is gone: the IMF/World Bank series sold as headline CPI matches
NCPI 2021=100 exactly for 2022-01..2024-08 (32/32 months) and CBSL's Colombo CPI exactly
for 2024-09..2026-06 (22/22). It silently switches index mid-series. It is not used.

Chain-link: the DCS vintages overlap across all of 2022, so the 2013-base leg is scaled by
(2022 mean on the 2021 base)/(2022 mean on the 2013 base) - an annual-average link, because
the 2021 vintage is a reweighted basket rather than a rebasing and the month-by-month ratio
drifts 2.0% (NCPI) across 2022. Scaled rows carry CHAIN_LINKED_2013_BASE.

Quarterly and annual are derived by period average over COMPLETE periods only (P1-02);
derived quarterly matched the publishers' own quarterly to 0.0000 for all four of the old
indices, confirming the publishers use a simple period average.
"""
import pandas as pd, pathlib, datetime, os

DATA = pathlib.Path(__file__).resolve().parents[2] / "Data"

# project code -> (source file, source label, [(date a vintage takes over, flag for periods BEFORE it)])
# Links are listed newest-first. A period earlier than a link date carries that link's flag,
# so CCPI's pre-2014 rows are marked as sitting two baskets back, not one.
TARGETS = {
    # The file names say what each series actually is; the dict key is the project's code.
    # HCPI (headline / all items) IS the DCS National CPI - see the note in the repo root.
    "HCPI": ("dcs_NCPI_monthly.csv", "dcs",
             [(pd.Timestamp("2022-01-01"), "CHAIN_LINKED_2013_BASE")]),
    "FCPI": ("dcs_FCPI_monthly.csv", "dcs",
             [(pd.Timestamp("2022-01-01"), "CHAIN_LINKED_2013_BASE")]),
    "CCPI": ("dcs_CCPI_monthly.csv", "dcs",
             [(pd.Timestamp("2022-01-01"), "CHAIN_LINKED_2013_BASE"),
              (pd.Timestamp("2014-01-01"), "CHAIN_LINKED_200607_BASE")]),
}
MONTHS = {"monthly": 1, "quarterly": 3, "annual": 12}
RULE = {"monthly": "MS", "quarterly": "QS", "annual": "YS"}
LAG = {"monthly": 12, "quarterly": 4, "annual": 1}
REQUIRED_END = {"monthly": "2026-08-01", "quarterly": "2026-04-01", "annual": "2025-01-01"}


def to_freq(s, freq):
    if freq == "monthly":
        return s
    g = s.resample(RULE[freq])
    out, n = g.mean(), g.count()
    return out[n == MONTHS[freq]]


def build(index):
    fn, src, links = TARGETS[index]
    m = pd.read_csv(DATA / fn, parse_dates=["date"]).set_index("date")["value"].dropna().sort_index()
    rows = []
    for freq in ["monthly", "quarterly", "annual"]:
        s = to_freq(m, freq)
        prev = None
        for d, v in s.items():
            lag_d = d - pd.DateOffset(months=MONTHS[freq] * LAG[freq])
            y = ((v / s[lag_d] - 1) * 100) if lag_d in s.index else None
            f = []
            period_end = d + pd.DateOffset(months=MONTHS[freq] - 1)
            # the most recent link the period sits behind is the one that describes it
            behind = [fl for lk, fl in links if period_end < lk]
            if behind:
                f.append(behind[-1])
            if y is None:
                f.append("NO_YOY_SOURCE_LAG")
            if freq == "monthly" and prev is not None and v == prev:
                f.append("REPEATED_VALUE")
            prev = v
            rows.append({"date": d.date().isoformat(), "frequency": freq, "index": index,
                         "value": round(float(v), 4), "unit": "index_level",
                         "yoy_pct": None if y is None else round(float(y), 4),
                         "source": src,
                         "derivation": "published" if freq == "monthly" else "period_average",
                         "flag": ";".join(f) if f else "OK"})
    return rows


def origins(first, last, freq):
    """How many of the plan's rolling origins this coverage supports.

    An origin S needs BOTH ends: training history before it and actuals to score it.
    Counting only the scoring end is the easy mistake - it makes a series that starts in
    2023 look like it supports a Jan-2020 origin. MIN_HISTORY is a floor, not the plan's
    expanding window, which would use everything from series start.
    """
    n_h, want = {"monthly": (12, 69), "quarterly": (4, 23), "annual": (1, 6)}[freq]
    MIN_HISTORY = {"monthly": 24, "quarterly": 8, "annual": 3}[freq]   # periods
    step = MONTHS[freq]
    first, last = pd.Timestamp(first), pd.Timestamp(last)
    starts = pd.date_range("2020-01-01", periods=want, freq=RULE[freq])
    ok = [S for S in starts
          if S - pd.DateOffset(months=step * MIN_HISTORY) >= first          # enough history
          and S + pd.DateOffset(months=step * (n_h - 1)) <= last]           # scoreable
    # note: `last` is a PERIOD START, so the horizon's end is step*(n_h-1) months on,
    # not step*n_h-1 - the latter silently drops the final quarterly and annual origin.
    return len(ok), want


def validate(df):
    pub = pd.read_csv(DATA / "cbsl_published_yoy.csv", parse_dates=["date"])
    pub = pub[pub["index"] == "HCPI"].assign(**{"index": "CCPI"})   # those rows are Colombo CPI
    m = df[(df.frequency == "monthly") & (df["index"] == "CCPI")].copy()
    m["date"] = pd.to_datetime(m["date"])
    j = m.merge(pub, on=["date", "index"]).dropna(subset=["yoy_pct"])
    g = (j["yoy_pct"] - j["published_yoy_pct"]).abs()
    return f"  CCPI computed vs CBSL printed YoY: n={len(j)} max gap={g.max():.3f}pp " \
           f"{'PASS (1dp rounding)' if g.max() <= 0.06 else 'CHECK'}"


def main():
    df = pd.DataFrame([r for i in TARGETS for r in build(i)])
    order = {"monthly": 0, "quarterly": 1, "annual": 2}
    df = df.sort_values(["index", "frequency", "date"],
                        key=lambda c: c.map(order) if c.name == "frequency" else c)
    out = pathlib.Path(os.environ.get("FINAL_DATA_OUT", DATA / "final_data.csv"))
    df.to_csv(out, index=False)
    print(f"wrote {out}  rows={len(df)}\n")
    print(f"{'index':6s}{'freq':11s}{'first':12s}{'last':12s}{'n':>5s}{'yoy_null':>10s}  origins")
    for (i, f), g in df.groupby(["index", "frequency"], sort=False):
        n, want = origins(g.date.min(), g.date.max(), f)
        ok = "OK" if g.date.max() >= REQUIRED_END[f] else "SHORT"
        print(f"{i:6s}{f:11s}{g.date.min():12s}{g.date.max():12s}{len(g):5d}"
              f"{int(g.yoy_pct.isna().sum()):10d}  {n}/{want} {ok}")
    print("\nflags:")
    print(df.flag.value_counts().to_string())
    print("\nvalidation:")
    print(validate(df))

    (DATA / "final_data_notes.md").write_text(f"""# final_data.csv

Generated {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ} by `Code/common/build_final_data.py`.
Provenance and ranges: `Data/methodology_data_collection.md`.

Tidy long format - one row per date x frequency x index. `value` is always an index level on
the **2021=100** base. `yoy_pct` is computed within the series and blank where no 12-month lag
exists.

## Targets

| Code | Meaning | Source | Range (monthly) |
|---|---|---|---|
| `HCPI` | Headline / all items = DCS **National** CPI - **main variable** | DCS, chain-linked | 2014-01 .. 2026-08 |
| `FCPI` | NCPI food group | DCS, chain-linked | 2014-01 .. 2026-08 |
| `CCPI` | **Colombo** CPI, all items - second headline target | DCS, chain-linked | 2014-01 .. 2026-08 |

`ECPI` is dropped: no publisher issues a Sri Lankan energy CPI.

`CCPI` here follows Sri Lankan convention (Colombo CPI). It is **not** the core measure the
abstract called CCPI; CBSL core is parked unused in `cbsl_CORE_monthly.csv`.

## Flags

| Flag | Meaning |
|---|---|
| `CHAIN_LINKED_2013_BASE` | period before 2022, scaled from the DCS 2013=100 vintage onto the 2021 base |
| `CHAIN_LINKED_200607_BASE` | CCPI before 2014, two baskets back: 2006/07=100 -> 2013=100 -> 2021=100 |
| `NO_YOY_SOURCE_LAG` | no 12-month lag in the series, so no rate |
| `REPEATED_VALUE` | repeats the previous month exactly |

## Deviation from the abstract

The abstract named HCPI, FCPI, CCPI (core) and ECPI. CCPI is now the **Colombo** CPI and ECPI
is dropped. See `INDEX_SET_CHANGE.md` in the repo root - this must be stated in the paper.
""", encoding="utf-8")


if __name__ == "__main__":
    main()
