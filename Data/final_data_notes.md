# final_data.csv

Generated 2026-09-22T16:13:53Z by `Code/common/build_final_data.py`.
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
