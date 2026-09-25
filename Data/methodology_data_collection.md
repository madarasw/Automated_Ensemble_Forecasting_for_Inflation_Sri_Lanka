# Data collection methodology

Covers activities **P1-01 to P1-04** of `Research.xlsx`. Companion files: `final_data_notes.md`
(the delivered dataset), `INDEX_SET_CHANGE.md` in the repo root (deviations from the abstract).

Scripts: `Code/common/parse_dcs_ncpi.py` (DCS PDF parsing and chain-linking),
`Code/common/build_final_data.py` (assembly). Output: `Data/final_data.csv`.

Retrieved 2026-09-22.

---

## 1. Targets

| Code | Series | Role |
|---|---|---|
| `HCPI` | Headline / all items = DCS **National** CPI (NCPI) | Main variable |
| `FCPI` | NCPI **food** group | Component target |
| `CCPI` | **Colombo** Consumer Price Index, all items | Second headline target |

`CCPI` follows Sri Lankan convention (Colombo CPI), not the abstract's "core". `ECPI` is
dropped — no publisher issues a Sri Lankan energy CPI. Both departures are recorded in
`INDEX_SET_CHANGE.md` and **must be stated in the paper**.

---

## 2. Sources — all primary, all Department of Census and Statistics

Every value in `final_data.csv` comes from a DCS publication. No World Bank, IMF or FRED data
is used (see §6 for why, and how they were used as checks).

| Series | Vintage | Source document | Range |
|---|---|---|---|
| NCPI all items, food, non-food | 2021=100 | `MovementsOf-NCPI.pdf`, `Inflation-FoodAndNonFoodGroups.pdf` | 2022-01 → 2026-08 |
| NCPI all items, food, non-food | 2013=100 | the same two, `-2013` editions | 2014-01 → 2022-12 |
| Colombo CPI | 2021=100 | `MOVEMENTS_of_CCPI_with_MV_Base2021.pdf` | 2022-01 → 2026-08 |
| Colombo CPI | 2013=100 | `MOVEMENTS_of_CCPI_with_MV_Base2013-100.pdf` | 2014-01 → 2023-01 |
| Colombo CPI | 2006/07=100 | `MovementsofCCPI_200607.pdf` | 2008-01 → 2016-12 (used 2012-09 → 2013-12) |

DCS index: https://www.statistics.gov.lk/InflationAndPrices/StaticalInformation/MonthlyNCPI
and `.../MonthlyCCPI`. The NCPI PDFs are held in `Data/`; CCPI tables were fetched from
statistics.gov.lk.

**Corroborating sources, not inputs**

| Source | Held in | Used for |
|---|---|---|
| CBSL press releases, Jul 2024 / Jul 2025 / Jul 2026 / Aug 2026 | `cbsl_CCPI_monthly.csv`, `cbsl_published_yoy.csv` | validating Colombo CPI levels and rates, 2023-07 → 2026-08 |
| CBSL press releases, Aug 2012 – Dec 2014 (31 PDFs) | `Data/pdfs/` | validating the 2006/07 extension, 2012-09 → 2013-10 |
| World Bank Global Inflation Database, manual download | `Inflation-data-manual_download_world_bank.xlsx` | independent check on HCPI and on the chain-link factor |

---

## 3. Method

**Parsing.** `pdftotext -layout`, separating index levels from rates by the percent sign
rather than by column position, which survives the ragged spacing. The All Items column was
cross-checked between the two DCS PDFs that both carry it: **max difference 0.0000 across 56
and 108 months**.

**Chain-linking.** Each older vintage is scaled by the ratio at the **first overlap month** —
the standard agency link, and the only one that preserves the old vintage's own growth rates
right up to the junction.

| Series | Link | Factor | Overlap | Seam MoM, linked vs source |
|---|---|---|---|---|
| HCPI | 2013 → 2021 @ 2022-01 | 0.793373 | 12 months | +3.106% vs +3.106% |
| FCPI | 2013 → 2021 @ 2022-01 | 0.805098 | 12 months | +3.405% vs +3.405% |
| CCPI | 2013 → 2021 @ 2022-01 | 0.784722 | 13 months | +2.391% vs +2.392% |
| CCPI | 2006/07 → 2013 @ 2014-01 | 0.587042 | 36 months | +0.567% vs +0.567% |

An annual-average link over the overlap was tried first and **rejected**: the newer vintages
are reweighted baskets, not rebasings, so the month-by-month ratio drifts (2.00% HCPI, 0.77%
FCPI, 2.25% CCPI at the 2013→2021 link, 2.81% at the 2006/07→2013 link) and an average link
put a spurious +3.6% step at Dec 2021 → Jan 2022 where DCS printed +3.1%.

**Aggregation.** Quarterly and annual derived by period average over **complete periods only**
(P1-02). Derived quarterly matched the publishers' own quarterly to 0.0000 for every index
tested, confirming a simple period average is the publishers' rule.

**Year-on-year** computed within the series; blank where no 12-month lag exists. Nothing is
interpolated; gaps stay visible.

---

## 4. Base

Each variable is on **one continuous scale for its whole length**, anchored to the published
2021=100 vintage. Verified:

- From 2022-01 our series is **identical** to the published 2021=100 vintage — max difference
  0.000000 across 56 months, for all three variables.
- At every link month the linked series reproduces the older vintage's own month-on-month
  change to three decimals (table above), so no artificial step was introduced.
- The three largest monthly moves in each series are all April–June 2022 — the genuine crisis,
  not a link artefact.

**One honest qualification.** "2021=100" names the anchor vintage; it is not a property the
back-cast years satisfy. Calendar-2021 means are HCPI 116.80, FCPI 128.14, CCPI 112.56, not
100, because DCS does not publish 2021 values on the 2021 basket — that table begins 2022-01 —
so pre-2022 values are the older basket scaled. This is what chain-linking always does and is
standard practice. It means **level comparisons across a link, or between variables, are not
meaningful; growth rates are.**

---

## 5. Validation performed

| Check | Result |
|---|---|
| NCPI/FCPI spot-checks against the DCS tables | 9/9 exact |
| All Items cross-checked between the two DCS PDFs per vintage | max diff 0.0000, n=56 and n=108 |
| DCS Colombo CPI vs 38 months transcribed from CBSL press releases | **exact on all 38** |
| Colombo CPI computed YoY vs CBSL printed rates | n=38, max gap 0.049pp (1dp rounding) |
| CBSL press releases (2012–13) vs DCS 2006/07 table | **exact on all 14 comparable months** |
| Dec 2013, derived from the printed 4.7% YoY on Dec 2012's 168.6 | 176.52 vs the table's 176.5 |
| Press-release overlaps | Jul 2024 = 194.7 and Jul 2025 = 194.1 each appear in two releases, consistent |
| World Bank HCPI vs ours, 2022-01 → 2024-10 | **exact, 34 months, zero difference** |
| World Bank HCPI vs ours, 2014-01 → 2021-12 | agreement to 0.003% — rounding only |
| World Bank's implied 2013→2021 link factor | 0.793354 vs our independently derived 0.793373 |
| Derived quarterly vs published quarterly | 0.0000 for every index |
| Date continuity | no gaps in any index × frequency |

---

## 6. Sources examined and rejected

- **World Bank FCPI.** Zero exact matches against DCS NCPI food over 135 months; ratio varies
  0.96923–1.03302, so it is a differently processed series, not a rebasing. Ends 2025-03.
- **World Bank HCPI as an input.** Before 2014 it is the **Colombo** CPI rescaled (ratio to our
  extended CCPI constant at 1.01064–1.01133), so the World Bank's "headline CPI" is itself an
  unflagged composite. After 2024-10 it runs 0.3–1.5% below DCS — a stale vintage.
- **An earlier World Bank/IMF vintage** pulled via API switches index mid-series: it matches
  NCPI exactly for 2022-01 → 2024-08 and the Colombo CPI exactly for 2024-09 → 2026-06. Used
  unmodified it reports −8.19% YoY for Dec 2024 against the published −1.7%. The manual
  download does **not** have this defect, so the fault is vintage-specific — name the vintage
  if the paper reports it.
- **IMF and World Bank monthly HCPI** (API vintage) are bit-for-bit identical, ratio 1.000000,
  sd 0.000000 over 182 months. They were never two independent sources.
- **FRED** returned only `FPCPITOTLZGLKA`, World Bank WDI republished, in percent not levels.
- **Annual sheets** in every API source and in the World Bank workbook are year-on-year
  **rates**, not index levels. Annual rows in `final_data.csv` are derived from monthly instead.

---

## 7. Coverage delivered

Required by the plan: monthly through Aug 2026, quarterly through 2026-Q2, annual through 2025.

| Variable | Monthly | Quarterly | Annual | Origins (M / Q / A) |
|---|---|---|---|---|
| HCPI | 2014-01 → 2026-08 (152) | 2014-Q1 → 2026-Q2 (50) | 2014 → 2025 (12) | 69/69 · 23/23 · 6/6 |
| FCPI | 2014-01 → 2026-08 (152) | 2014-Q1 → 2026-Q2 (50) | 2014 → 2025 (12) | 69/69 · 23/23 · 6/6 |
| CCPI | 2012-09 → 2026-08 (168) | 2012-Q4 → 2026-Q2 (55) | 2013 → 2025 (13) | 69/69 · 23/23 · 6/6 |

All three meet the experiment plan in full at every frequency.

**Training-window support at R4's first origin** (train cut-off Dec 2022), for the fixed-window
design: HCPI and FCPI have 108 months, CCPI has 124.

---

## 8. What the data supports for the experiment design

Maximum monthly history available at each origin: HCPI and FCPI 72 (origin 1) to 140 (origin 69);
CCPI 88 to 156. This sets which training windows are reachable:

| Monthly window | HCPI/FCPI origins | Earliest regime reached |
|---|---|---|
| 124 (100+24) | 17 | R5 |
| 100 | 41 | R3 |
| 72 (48+24) | **69 - all** | **R1** |

Only the 72-period window spans all six regimes. See `INDEX_SET_CHANGE.md` for how the
experiment blocks use this.

## 8. Known limitations

1. **Nov 2013 (CCPI) rests on a single source.** The Nov 2013 CBSL release prints no index
   level and no usable rate. The fifteen surrounding months match two sources exactly.
2. **HCPI and FCPI cannot start before 2014-01.** The NCPI did not exist; DCS publishes no
   earlier vintage. A 124-month window is therefore available for CCPI only.
3. **CCPI spans three baskets** (2006/07 → 2013 → 2021) across two links; HCPI and FCPI span
   two across one. Growth rates are preserved everywhere, but a 124-month CCPI window reaches
   through both links while a 72- or 108-month window reaches through one — so a 72-vs-124
   accuracy difference confounds extra history with extra splice. The **108-month window is the
   clean comparator**: at R4's first origin it begins Jan 2014, the vintage boundary itself.
4. **Back-cast years do not satisfy the 2021=100 identity** (§4). Compare growth, not levels.
