"""Parse the DCS NCPI publication PDFs in Data/ into tidy CSVs, and chain-link the
2013=100 and 2021=100 vintages into one continuous NCPI series on the 2021 base.

Inputs  (Data/):
  MovementsOf-NCPI.pdf              All Items, 2021=100
  MovementsOf-NCPI-2013.pdf         All Items, 2013=100
  Inflation-FoodAndNonFoodGroups.pdf       All Items / Food / Non-Food, 2021=100
  Inflation-FoodAndNonFoodGroups-2013.pdf  All Items / Food / Non-Food, 2013=100

Outputs (Data/):
  dcs_ncpi2021_{HCPI,FCPI,NFCPI}_monthly.csv   as published
  dcs_ncpi2013_{HCPI,FCPI,NFCPI}_monthly.csv   as published
  dcs_HCPI_monthly.csv / dcs_FCPI_monthly.csv  chain-linked, 2021=100, 2014-01 onward

Chain-link: the two vintages overlap for all of 2022. Each 2013-base leg is scaled by the
ratio at the FIRST overlap month (Jan 2022), which is the standard agency link and the only
one that preserves the old vintage's own growth rates right up to the junction. An
annual-average link over 2022 was tried first and rejected: because the 2021 vintage is a
reweighted basket rather than a rebasing, the month-by-month ratio drifts ~2% across 2022,
and an average link puts a spurious +3.6% month-on-month step at Dec 2021 -> Jan 2022 where
DCS printed +3.1%. Both factors are reported below so the choice is auditable.
"""
import re, subprocess, pathlib, pandas as pd

DATA = pathlib.Path(__file__).resolve().parents[2] / "Data"
MONTHS = {m: i + 1 for i, m in enumerate(
    "January February March April May June July August September October November December".split())}


def text(pdf):
    return subprocess.run(["pdftotext", "-layout", str(DATA / pdf), "-"],
                          capture_output=True, text=True, check=True).stdout


def parse(pdf, n_series):
    """Rows are 'Year Month v1 [pcts] v2 [pcts] ...'; the year is printed once per year.
    Index values are the tokens WITHOUT a percent sign - that separation is what makes
    this robust to the ragged column spacing."""
    out, year = [], None
    for line in text(pdf).splitlines():
        if not line.strip():
            continue
        y = re.match(r"\s*(19|20)(\d{2})\s", line)
        if y:
            year = int(y.group(0))
        m = re.search(r"\b(" + "|".join(MONTHS) + r")\b", line)
        if not m or year is None:
            continue
        tail = line[m.end():]
        vals = [float(t) for t in re.findall(r"-?\d+\.\d+(?!%)", tail) if not t.endswith("%")]
        vals = [float(t) for t in re.findall(r"(?<![\d.%-])(-?\d+\.\d)(?!\d*%)", tail)]
        if len(vals) < n_series:
            continue
        out.append({"date": f"{year}-{MONTHS[m.group(1)]:02d}-01", **
                    {f"v{i}": vals[i] for i in range(n_series)}})
    df = pd.DataFrame(out)
    df["date"] = pd.to_datetime(df["date"])
    return df.drop_duplicates("date").set_index("date").sort_index()


def save(s, name):
    s.rename("value").to_frame().to_csv(DATA / name, float_format="%g")
    print(f"  {name:38s} {len(s):4d} rows  {s.index.min():%Y-%m} .. {s.index.max():%Y-%m}")


def main():
    print("parsing 2021=100 (All Items / Food / Non-Food):")
    g21 = parse("Inflation-FoodAndNonFoodGroups.pdf", 3)
    print("parsing 2013=100 (All Items / Food / Non-Food):")
    g13 = parse("Inflation-FoodAndNonFoodGroups-2013.pdf", 3)
    mv21 = parse("MovementsOf-NCPI.pdf", 1)
    mv13 = parse("MovementsOf-NCPI-2013.pdf", 1)

    # cross-check the All Items column against the standalone Movements tables
    for label, a, b in [("2021", g21["v0"], mv21["v0"]), ("2013", g13["v0"], mv13["v0"])]:
        j = pd.concat([a.rename("grp"), b.rename("mov")], axis=1).dropna()
        d = (j["grp"] - j["mov"]).abs().max()
        print(f"  cross-check All Items {label}=100 across the two PDFs: n={len(j)} "
              f"max diff={d:.4f} {'MATCH' if d < 1e-9 else 'DIFFERS'}")

    names = {"v0": "HCPI", "v1": "FCPI", "v2": "NFCPI"}
    print("\nas published:")
    for col, nm in names.items():
        save(g21[col].dropna(), f"dcs_ncpi2021_{nm}_monthly.csv")
        save(g13[col].dropna(), f"dcs_ncpi2013_{nm}_monthly.csv")

    print("\nchain-link factors (2021 base / 2013 base):")
    linked = {}
    for col, nm in names.items():
        new, old = g21[col].dropna(), g13[col].dropna()
        link = new.index.min()                       # Jan 2022, first overlap month
        f = new[link] / old[link]
        f_avg = new["2022"].mean() / old["2022"].mean()
        ratio = (new["2022"] / old["2022"])
        print(f"  {nm:6s} link@{link:%Y-%m} factor={f:.6f}  (annual-average alternative "
              f"{f_avg:.6f})  2022 ratio spans {ratio.min():.5f}..{ratio.max():.5f} "
              f"(drift {100*(ratio.max()/ratio.min()-1):.2f}%)")
        linked[nm] = pd.concat([(old[old.index < "2022-01-01"] * f), new]).sort_index()
    print("\nchain-linked, 2021=100:")
    for nm in ["HCPI", "FCPI"]:
        save(linked[nm].round(4), f"dcs_{'NCPI' if nm == 'HCPI' else nm}_monthly.csv")

    # what the legacy IMF/World Bank series actually is
    imf = pd.read_csv(DATA / "imf_HCPI_monthly.csv", parse_dates=["date"]).set_index("date")["value"]
    ncpi, cbsl = g21["v0"], pd.read_csv(DATA / "cbsl_CCPI_monthly.csv",
                                        parse_dates=["date"]).set_index("date")["value"]
    print("\nidentity of the legacy IMF/World Bank HCPI series:")
    for lbl, ref in [("NCPI 2021=100", ncpi), ("CBSL Colombo CPI 2021=100", cbsl)]:
        j = pd.concat([imf.rename("imf"), ref.rename("ref")], axis=1).dropna()
        eq = (j["imf"] - j["ref"]).abs() < 1e-9
        if len(j):
            spans = j.index[eq]
            print(f"  vs {lbl:22s} overlap n={len(j):3d}  exact matches={int(eq.sum()):3d}"
                  + (f"  ({spans.min():%Y-%m} .. {spans.max():%Y-%m})" if eq.any() else ""))


if __name__ == "__main__":
    main()
