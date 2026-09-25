# Source comparison

Generated 2026-09-22T08:48:08Z by `fetch_data.py`.

All series normalised to year-on-year percent change before comparison (index-level series converted via period-over-period-a-year-ago percent change; series already published as YoY percent are used as-is). This normalisation is for comparison only — the saved CSVs keep each source's as-published units unconverted.


## HCPI / monthly

**Coverage:**

| Source | First date | Last date |
|---|---|---|
| imf | 2010-01-01 | 2026-06-01 |
| worldbank | 2010-01-01 | 2025-02-01 |

**`imf` vs `worldbank`** (overlap 2011-01-01 → 2025-02-01, n=170)
- mean |diff| = 0.000pp, max |diff| = 0.000pp
- rank correlation (Spearman) = 1.0000
- dates differing by >0.1pp: 0 (0 of those fall in the 2020-2026 evaluation window)

**Verdict:** 
Sources broadly agree (worst pairwise max diff 0.00pp, imf vs worldbank). None of the notable divergence dates fall inside the 2020-2026 evaluation window.

## HCPI / quarterly

**Coverage:**

| Source | First date | Last date |
|---|---|---|
| imf | 2010-01-01 | 2026-04-01 |
| worldbank | 2010-01-01 | 2024-10-01 |

**`imf` vs `worldbank`** (overlap 2011-01-01 → 2024-10-01, n=56)
- mean |diff| = 0.000pp, max |diff| = 0.000pp
- rank correlation (Spearman) = 1.0000
- dates differing by >0.1pp: 0 (0 of those fall in the 2020-2026 evaluation window)

**Verdict:** 
Sources broadly agree (worst pairwise max diff 0.00pp, imf vs worldbank). None of the notable divergence dates fall inside the 2020-2026 evaluation window.

## HCPI / annual

**Coverage:**

| Source | First date | Last date |
|---|---|---|
| fred | 1960-01-01 | 2025-01-01 |
| imf | 2010-01-01 | 2025-01-01 |
| worldbank | 1970-01-01 | 2024-01-01 |

**`fred` vs `imf`** (overlap 2011-01-01 → 2025-01-01, n=15)
- mean |diff| = 0.000pp, max |diff| = 0.000pp
- rank correlation (Spearman) = 1.0000
- dates differing by >0.1pp: 0 (0 of those fall in the 2020-2026 evaluation window)

**`fred` vs `worldbank`** (overlap 1970-01-01 → 2024-01-01, n=55)
- mean |diff| = 0.466pp, max |diff| = 12.928pp
- rank correlation (Spearman) = 0.9777
- dates differing by >0.1pp: 9 (2 of those fall in the 2020-2026 evaluation window)
  2003-01-01: 2.65pp; 2004-01-01: 1.44pp; 2005-01-01: 0.66pp; 2008-01-01: 12.93pp; 2014-01-01: 0.34pp; 2017-01-01: 1.12pp; 2019-01-01: 0.77pp; 2022-01-01: 4.77pp; 2023-01-01: 0.82pp

**`imf` vs `worldbank`** (overlap 2011-01-01 → 2024-01-01, n=14)
- mean |diff| = 0.563pp, max |diff| = 4.772pp
- rank correlation (Spearman) = 0.9429
- dates differing by >0.1pp: 5 (2 of those fall in the 2020-2026 evaluation window)
  2014-01-01: 0.34pp; 2017-01-01: 1.12pp; 2019-01-01: 0.77pp; 2022-01-01: 4.77pp; 2023-01-01: 0.82pp

**Verdict:** 
Sources diverge meaningfully at times (worst pairwise max diff 12.93pp, fred vs worldbank). 2 of the >0.1pp divergence dates fall inside the 2020-2026 evaluation window — this matters more than agreement or disagreement outside it (pre-2020 divergence is much lower stakes for this study).

## FCPI / monthly

**Coverage:**

| Source | First date | Last date |
|---|---|---|
| imf | 2014-01-01 | 2024-08-01 |
| worldbank | 2014-01-01 | 2025-03-01 |

**`imf` vs `worldbank`** (overlap 2015-01-01 → 2024-08-01, n=116)
- mean |diff| = 0.226pp, max |diff| = 1.012pp
- rank correlation (Spearman) = 0.9990
- dates differing by >0.1pp: 69 (45 of those fall in the 2020-2026 evaluation window)
  2015-01-01: 0.11pp; 2016-05-01: 0.10pp; 2016-07-01: 0.23pp; 2016-10-01: 0.27pp; 2017-04-01: 0.21pp; 2017-08-01: 0.36pp; 2017-09-01: 0.34pp; 2017-10-01: 0.48pp; 2017-11-01: 0.37pp; 2017-12-01: 0.23pp; 2018-04-01: 0.13pp; 2018-07-01: 0.10pp; 2018-08-01: 0.39pp; 2018-09-01: 0.36pp; 2018-10-01: 0.15pp …

**Verdict:** 
Sources diverge meaningfully at times (worst pairwise max diff 1.01pp, imf vs worldbank). 45 of the >0.1pp divergence dates fall inside the 2020-2026 evaluation window — this matters more than agreement or disagreement outside it (pre-2020 divergence is much lower stakes for this study).

## FCPI / quarterly

**Coverage:**

| Source | First date | Last date |
|---|---|---|
| imf | 2014-01-01 | 2024-04-01 |
| worldbank | 2014-01-01 | 2025-01-01 |

**`imf` vs `worldbank`** (overlap 2015-01-01 → 2024-04-01, n=38)
- mean |diff| = 0.195pp, max |diff| = 0.727pp
- rank correlation (Spearman) = 0.9985
- dates differing by >0.1pp: 22 (16 of those fall in the 2020-2026 evaluation window)
  2017-01-01: 0.12pp; 2017-07-01: 0.23pp; 2018-07-01: 0.24pp; 2018-10-01: 0.11pp; 2019-07-01: 0.49pp; 2019-10-01: 0.24pp; 2020-01-01: 0.22pp; 2020-04-01: 0.11pp; 2020-07-01: 0.65pp; 2020-10-01: 0.31pp; 2021-01-01: 0.30pp; 2021-07-01: 0.73pp; 2021-10-01: 0.39pp; 2022-01-01: 0.30pp; 2022-04-01: 0.15pp …

**Verdict:** 
Sources diverge meaningfully at times (worst pairwise max diff 0.73pp, imf vs worldbank). 16 of the >0.1pp divergence dates fall inside the 2020-2026 evaluation window — this matters more than agreement or disagreement outside it (pre-2020 divergence is much lower stakes for this study).

## FCPI / annual

**Coverage:**

| Source | First date | Last date |
|---|---|---|
| imf | 2014-01-01 | 2023-01-01 |
| worldbank | 1970-01-01 | 2023-01-01 |

**`imf` vs `worldbank`** (overlap 2015-01-01 → 2023-01-01, n=9)
- mean |diff| = 0.017pp, max |diff| = 0.138pp
- rank correlation (Spearman) = 1.0000
- dates differing by >0.1pp: 1 (1 of those fall in the 2020-2026 evaluation window)
  2022-01-01: 0.14pp

**Verdict:** 
Sources broadly agree (worst pairwise max diff 0.14pp, imf vs worldbank). 1 of the >0.1pp divergence dates fall inside the 2020-2026 evaluation window — this matters more than agreement or disagreement outside it (pre-2020 divergence is much lower stakes for this study).

## CCPI / monthly

**Coverage:**

| Source | First date | Last date |
|---|---|---|
| worldbank | 2014-01-01 | 2025-03-01 |

Only one source (`worldbank`) publishes this index/frequency combination — no cross-source comparison is possible. This is a coverage finding in its own right (see coverage_report.md).

## CCPI / quarterly

**Coverage:**

| Source | First date | Last date |
|---|---|---|
| worldbank | 2014-01-01 | 2025-01-01 |

Only one source (`worldbank`) publishes this index/frequency combination — no cross-source comparison is possible. This is a coverage finding in its own right (see coverage_report.md).

## CCPI / annual

**Coverage:**

| Source | First date | Last date |
|---|---|---|
| worldbank | 2009-01-01 | 2024-01-01 |

Only one source (`worldbank`) publishes this index/frequency combination — no cross-source comparison is possible. This is a coverage finding in its own right (see coverage_report.md).

## ECPI / monthly

**Coverage:**

| Source | First date | Last date |
|---|---|---|
| worldbank | 2014-01-01 | 2024-08-01 |

Only one source (`worldbank`) publishes this index/frequency combination — no cross-source comparison is possible. This is a coverage finding in its own right (see coverage_report.md).

## ECPI / quarterly

**Coverage:**

| Source | First date | Last date |
|---|---|---|
| worldbank | 2014-01-01 | 2024-04-01 |

Only one source (`worldbank`) publishes this index/frequency combination — no cross-source comparison is possible. This is a coverage finding in its own right (see coverage_report.md).

## ECPI / annual

**Coverage:**

| Source | First date | Last date |
|---|---|---|
| worldbank | 1970-01-01 | 2024-01-01 |

Only one source (`worldbank`) publishes this index/frequency combination — no cross-source comparison is possible. This is a coverage finding in its own right (see coverage_report.md).
