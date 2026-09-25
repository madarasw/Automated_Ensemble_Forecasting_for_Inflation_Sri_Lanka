#!/usr/bin/env python3
"""
fetch_data.py — Sri Lanka CPI data acquisition (P1-01 .. P1-04)

Downloads four Sri Lankan consumer price indices (HCPI headline, FCPI food,
CCPI core, ECPI energy) at three frequencies (monthly, quarterly, annual)
from THREE independent sources — FRED, the IMF, and the World Bank Global
Database of Inflation — and saves each source separately. This script does
NOT pick a winning source; it produces the evidence (source_comparison.*)
so a human can.

Output (all under Data/, next to this script):
    fred_<INDEX>_<freq>.csv        worldbank_<INDEX>_<freq>.csv
    imf_<INDEX>_<freq>.csv         (date,value — ISO period-start dates)
    sources.md                     one entry per series: ID, title, units,
                                    base year, URL, vintage, download time
    coverage_report.md             first/last date, obs count, gaps,
                                    base-year breaks, short-of-requirement flags
    source_comparison.md / .csv    cross-source reconciliation, normalised
                                    to year-on-year percent change
    raw/                           cached raw API/file responses (gitignored
                                    separately — see .gitignore note below)

How to run
----------
    python fetch_data.py                              # fetch everything
    python fetch_data.py --source fred                # one source only
    python fetch_data.py --index HCPI --frequency monthly
    python fetch_data.py --force                       # ignore raw cache,
                                                         # re-hit every API

Flags: --source {fred,imf,worldbank,all} (default all)
       --index  {HCPI,FCPI,CCPI,ECPI,all} (default all)
       --frequency {monthly,quarterly,annual,all} (default all)
       --force  bypass the raw-response cache under Data/raw/ and re-fetch

Getting a FRED API key (free, instant)
---------------------------------------
    1. Create a free account at https://fredaccount.stlouisfed.org/apikeys
    2. Request an API key (instant, no approval wait)
    3. Set it in your shell before running this script:
         macOS/Linux : export FRED_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
         Windows PS  : $env:FRED_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    The script never hardcodes or logs the key, and fails immediately with
    a clear message if --source fred/all is requested and the variable is
    unset.

Requirements: Python standard library + requests, pandas, openpyxl.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR
RAW_DIR = DATA_DIR / "raw"

INDICES = ["HCPI", "FCPI", "CCPI", "ECPI"]
FREQUENCIES = ["monthly", "quarterly", "annual"]
SOURCES = ["fred", "imf", "worldbank"]

# Minimum end points the experiment plan requires (period-start dates).
REQUIRED_END = {
    "monthly": date(2026, 8, 1),     # T*-M-069 needs Sep2025-Aug2026 actuals
    "quarterly": date(2026, 4, 1),   # Q2 2026
    "annual": date(2025, 1, 1),      # 2025
}
REQUIRED_END_LABEL = {
    "monthly": "Aug 2026",
    "quarterly": "Q2 2026",
    "annual": "2025",
}

HTTP_TIMEOUT = 40
MAX_RETRIES = 5
USER_AGENT = "Central-Bank-Research-fetch_data/1.0 (research script; contact via repo)"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fetch_data")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Result / logging data structures
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    source: str
    index: str
    frequency: str
    identifier: str
    title: str
    chosen: bool
    reason: str


@dataclass
class SeriesResult:
    source: str
    index: str
    frequency: str
    status: str  # OK, SHORT, MISSING, ERROR
    series_id: Optional[str] = None
    title: Optional[str] = None
    units: Optional[str] = None
    base_year: Optional[str] = None
    url: Optional[str] = None
    vintage: Optional[str] = None
    downloaded_at: Optional[str] = None
    obs_count: int = 0
    first_date: Optional[date] = None
    last_date: Optional[date] = None
    gaps: list = field(default_factory=list)       # list of (start,end) gap dates
    base_year_breaks: list = field(default_factory=list)  # list of dates
    note: str = ""
    df: Optional[pd.DataFrame] = None   # date,value — only set when status OK/SHORT
    unit_type: Optional[str] = None     # "index" or "yoy_pct" — used for comparison


CANDIDATES_LOG: list[Candidate] = []
RESULTS: dict[tuple, SeriesResult] = {}
FAILURES: list[str] = []


def log_candidate(source, index, frequency, identifier, title, chosen, reason):
    CANDIDATES_LOG.append(Candidate(source, index, frequency, identifier, title, chosen, reason))


# ---------------------------------------------------------------------------
# HTTP helper with retry/backoff
# ---------------------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


def http_get(url, params=None, headers=None, source="?", allow_statuses=()):
    """GET with exponential backoff on timeouts/429/5xx. Returns a Response.

    `allow_statuses` lets a caller treat specific non-2xx codes as a normal
    (non-retried) outcome it will inspect itself, e.g. the IMF API's known
    HTTP 400 on an empty result set.
    """
    backoff = 1.5
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = SESSION.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            last_exc = exc
            log.warning("%s: network error (%s), attempt %d/%d", source, exc, attempt, MAX_RETRIES)
            time.sleep(backoff)
            backoff *= 2
            continue

        if resp.status_code in allow_statuses:
            return resp
        if resp.status_code == 429 or resp.status_code >= 500:
            last_exc = f"HTTP {resp.status_code}"
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else backoff
            log.warning("%s: HTTP %d, retrying in %.1fs (attempt %d/%d)",
                        source, resp.status_code, wait, attempt, MAX_RETRIES)
            time.sleep(wait)
            backoff *= 2
            continue
        return resp
    raise RuntimeError(f"{source}: exceeded {MAX_RETRIES} retries (last failure: {last_exc})")


# ---------------------------------------------------------------------------
# Raw-response cache under Data/raw/
# ---------------------------------------------------------------------------

def cache_path(source: str, key: str, ext: str) -> Path:
    d = RAW_DIR / source
    d.mkdir(parents=True, exist_ok=True)
    safe_key = key.replace("/", "_").replace(":", "_").replace(",", "_").replace("?", "_")
    if len(safe_key) > 120:
        safe_key = safe_key[:80] + "_" + hashlib.sha1(safe_key.encode()).hexdigest()[:16]
    return d / f"{safe_key}.{ext}"


def cache_read_json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def cache_write_json(path: Path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def cache_read_bytes(path: Path):
    if path.exists():
        return path.read_bytes()
    return None


def cache_write_bytes(path: Path, data: bytes):
    path.write_bytes(data)


# ---------------------------------------------------------------------------
# Date helpers — uniform output schema
# ---------------------------------------------------------------------------

def period_range(freq: str, start: date, end: date) -> list[date]:
    """Full list of period-start dates from start to end inclusive, at freq."""
    out = []
    if freq == "monthly":
        y, m = start.year, start.month
        while (y, m) <= (end.year, end.month):
            out.append(date(y, m, 1))
            m += 1
            if m > 12:
                m = 1
                y += 1
    elif freq == "quarterly":
        y, q = start.year, (start.month - 1) // 3 + 1
        ey, eq = end.year, (end.month - 1) // 3 + 1
        while (y, q) <= (ey, eq):
            out.append(date(y, (q - 1) * 3 + 1, 1))
            q += 1
            if q > 4:
                q = 1
                y += 1
    elif freq == "annual":
        for y in range(start.year, end.year + 1):
            out.append(date(y, 1, 1))
    else:
        raise ValueError(freq)
    return out


def build_series_df(freq: str, date_values: dict[date, float]) -> pd.DataFrame:
    """Reindex sparse (date -> value) onto the FULL period grid from first to
    last observed date, so genuine gaps show up as blank rows instead of
    being silently omitted."""
    if not date_values:
        return pd.DataFrame(columns=["date", "value"])
    dates = sorted(date_values.keys())
    full_grid = period_range(freq, dates[0], dates[-1])
    rows = [(d, date_values.get(d)) for d in full_grid]
    df = pd.DataFrame(rows, columns=["date", "value"])
    return df


def find_gaps(df: pd.DataFrame) -> list[str]:
    gaps = []
    if df.empty:
        return gaps
    missing = df[df["value"].isna()]
    for d in missing["date"]:
        gaps.append(d.isoformat())
    return gaps


def detect_base_year_breaks(df: pd.DataFrame, unit_type: str, drop_threshold: float = -0.20,
                             rise_threshold: float = 0.25, near_100_band: float = 5.0) -> list[str]:
    """Heuristic screen for a level discontinuity that looks like a rebasing
    rather than a genuine price movement: only meaningful for index-level
    series. Sri Lanka had genuine ~50% YoY inflation in 2022, so a plain
    "big jump" threshold flags the 2022 crisis as a false positive on every
    index-level series. Rebasing conventionally resets the index to (near)
    100, and inflation almost never produces a large single-period *drop*
    (Sri Lanka's worst deflation on record is a few percent), so a jump is
    only flagged here if it is a steep drop, or if it lands close to 100 —
    both are rebase signatures that ordinary inflation does not produce."""
    if unit_type != "index" or df.empty:
        return []
    s = df.set_index("date")["value"].astype(float)
    pct = s.pct_change()
    is_drop = pct < drop_threshold
    lands_near_100 = (pct.abs() > rise_threshold) & ((s - 100).abs() < near_100_band)
    flagged = pct[is_drop | lands_near_100]
    return [d.isoformat() for d in flagged.index]


# ===========================================================================
# FRED
# ===========================================================================

FRED_BASE = "https://api.stlouisfed.org/fred"
FRED_FREQ_LABEL = {"monthly": "Monthly", "quarterly": "Quarterly", "annual": "Annual"}
FRED_QUERIES = {
    "HCPI": ["Sri Lanka consumer price index", "Sri Lanka consumer prices",
             "Sri Lanka inflation", "Sri Lanka CPI"],
    "FCPI": ["Sri Lanka food price index", "Sri Lanka food CPI", "Sri Lanka food inflation"],
    "CCPI": ["Sri Lanka core inflation", "Sri Lanka core CPI",
             "Sri Lanka core consumer price index"],
    "ECPI": ["Sri Lanka energy price index", "Sri Lanka energy CPI", "Sri Lanka energy inflation"],
}

# FRED's full-text search matches loosely on words like "consumer"/"consumption",
# which pulls in unrelated national-accounts and financial-sector series (e.g.
# "Price Level of Government Consumption for Sri Lanka" is a Penn-World-Table
# relative price-level series, not a CPI). Require the returned series title to
# actually be about a price index/inflation measure, and explicitly reject the
# known false-positive families rather than trusting frequency + country alone.
FRED_CPI_HINTS = ("consumer price", "cpi", "price index", "inflation")
FRED_INDEX_HINTS = {
    "HCPI": (),  # the CPI hints alone are enough for headline
    "FCPI": ("food",),
    "CCPI": ("core",),
    "ECPI": ("energy",),
}
FRED_EXCLUDE_HINTS = (
    "price level of", "purchasing power parity", "gdp per capita",
    "stock market", "deposits to gdp", "credit by deposit", "debt securities",
    "capitalization", "liquid liabilities", "central bank assets", "turnover ratio",
    "exchange rate", "export", "import",
)


def fred_title_is_relevant(index: str, title: str) -> tuple[bool, str]:
    t = title.lower()
    if any(bad in t for bad in FRED_EXCLUDE_HINTS):
        return False, "title matches a known non-CPI false-positive pattern"
    if not any(h in t for h in FRED_CPI_HINTS):
        return False, "title does not look like a price index / inflation series"
    extra = FRED_INDEX_HINTS[index]
    if extra and not any(h in t for h in extra):
        return False, f"title does not mention {'/'.join(extra)}"
    return True, "title matches expected topic"


def fred_api_key() -> str:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise SystemExit(
            "FRED_API_KEY environment variable is not set.\n"
            "Get a free key at https://fredaccount.stlouisfed.org/apikeys and set it:\n"
            "  macOS/Linux : export FRED_API_KEY=your_key_here\n"
            "  Windows PS  : $env:FRED_API_KEY = \"your_key_here\"\n"
            "Re-run with --source imf,worldbank to skip FRED without a key."
        )
    return key


def fred_search(query: str, api_key: str, force: bool) -> dict:
    key = "search_" + hashlib.sha1(query.encode()).hexdigest()[:20]
    cpath = cache_path("fred", key, "json")
    if not force:
        cached = cache_read_json(cpath)
        if cached is not None:
            return cached
    resp = http_get(f"{FRED_BASE}/series/search",
                     params={"search_text": query, "api_key": api_key,
                             "file_type": "json", "limit": 100},
                     source="fred-search")
    resp.raise_for_status()
    data = resp.json()
    cache_write_json(cpath, data)
    return data


def fred_observations(series_id: str, api_key: str, force: bool) -> dict:
    cpath = cache_path("fred", f"obs_{series_id}", "json")
    if not force:
        cached = cache_read_json(cpath)
        if cached is not None:
            return cached
    resp = http_get(f"{FRED_BASE}/series/observations",
                     params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
                     source="fred-obs")
    resp.raise_for_status()
    data = resp.json()
    cache_write_json(cpath, data)
    return data


def fred_fetch_series(index: str, frequency: str, api_key: str, force: bool) -> SeriesResult:
    target_freq = FRED_FREQ_LABEL[frequency]
    seen: dict[str, dict] = {}
    for q in FRED_QUERIES[index]:
        try:
            data = fred_search(q, api_key, force)
        except Exception as exc:
            log.warning("FRED search failed for %r: %s", q, exc)
            continue
        for s in data.get("seriess", []):
            seen[s["id"]] = s

    eligible = []
    for sid, s in seen.items():
        is_sl = "sri lanka" in s["title"].lower()
        freq_ok = s.get("frequency") == target_freq
        discontinued = "(DISCONTINUED)" in s["title"]
        relevant, relevance_reason = fred_title_is_relevant(index, s["title"])
        ok = is_sl and freq_ok and not discontinued and relevant
        reason_bits = []
        if not is_sl:
            reason_bits.append("title does not mention Sri Lanka")
        if not freq_ok:
            reason_bits.append(f"frequency is {s.get('frequency')!r}, need {target_freq!r}")
        if discontinued:
            reason_bits.append("marked DISCONTINUED")
        if not relevant:
            reason_bits.append(relevance_reason)
        reason = "candidate accepted" if ok else "rejected: " + "; ".join(reason_bits)
        log_candidate("fred", index, frequency, sid, s["title"], chosen=False, reason=reason)
        if ok:
            eligible.append((sid, s))

    if not eligible:
        note = (f"No FRED series found for Sri Lanka {index} at {frequency} frequency after "
                f"searching {len(FRED_QUERIES[index])} query terms ({len(seen)} unique series "
                f"inspected). See sources.md candidate log for full detail.")
        log.info("FRED %s/%s: UNAVAILABLE — %s", index, frequency, note)
        return SeriesResult("fred", index, frequency, "MISSING", note=note)

    def score(item):
        sid, s = item
        try:
            start = datetime.fromisoformat(s["observation_start"]).date()
            end = datetime.fromisoformat(s["observation_end"]).date()
            span_days = (end - start).days
        except Exception:
            span_days = 0
        penalize_projection = "projections" in (s.get("notes") or "").lower()
        return (not penalize_projection, span_days)

    eligible.sort(key=score, reverse=True)
    chosen_id, chosen = eligible[0]

    for cand in CANDIDATES_LOG:
        if cand.source == "fred" and cand.index == index and cand.frequency == frequency \
                and cand.identifier == chosen_id:
            cand.chosen = True
            cand.reason = "chosen: longest verified span among eligible Sri Lanka candidates"

    try:
        obs_data = fred_observations(chosen_id, api_key, force)
    except Exception as exc:
        FAILURES.append(f"FRED {index}/{frequency}: failed to fetch observations for {chosen_id}: {exc}")
        return SeriesResult("fred", index, frequency, "ERROR", series_id=chosen_id,
                             title=chosen["title"], note=str(exc))

    date_values = {}
    for o in obs_data.get("observations", []):
        if o["value"] in (".", "", None):
            continue
        d = datetime.fromisoformat(o["date"]).date()
        date_values[d] = float(o["value"])

    if not date_values:
        note = f"Series {chosen_id} resolves but returned zero usable observations."
        return SeriesResult("fred", index, frequency, "MISSING", series_id=chosen_id,
                             title=chosen["title"], note=note)

    units = chosen.get("units", "")
    unit_type = "yoy_pct" if "percent" in units.lower() else "index"
    base_year = None
    m = None
    if unit_type == "index":
        import re
        m = re.search(r"(\d{4})=100", units)
        base_year = m.group(1) if m else None

    df = build_series_df(frequency, date_values)
    required_end = REQUIRED_END[frequency]
    status = "OK" if df["date"].max() >= required_end else "SHORT"

    return SeriesResult(
        source="fred", index=index, frequency=frequency, status=status,
        series_id=chosen_id, title=chosen["title"], units=units, base_year=base_year,
        url=f"https://fred.stlouisfed.org/series/{chosen_id}",
        vintage=f"last_updated={chosen.get('last_updated')}",
        downloaded_at=utcnow_iso(), obs_count=int(df["value"].notna().sum()),
        first_date=df["date"].min(), last_date=df["date"].max(),
        gaps=find_gaps(df), base_year_breaks=detect_base_year_breaks(df, unit_type),
        df=df, unit_type=unit_type,
        note=f"Source note: {(chosen.get('notes') or '')[:300]}",
    )


# ===========================================================================
# IMF — SDMX 2.1 REST API at api.imf.org (current live service; the old
# dataservices.imf.org SDMX_JSON.svc endpoint is dead and is NOT used here)
# ===========================================================================

IMF_BASE = "https://api.imf.org/external/sdmx/2.1"
IMF_DATAFLOW = "IMF.STA,CPI,5.0.0"
IMF_FREQ_CODE = {"monthly": "M", "quarterly": "Q", "annual": "A"}

# (INDEX_TYPE, COICOP_1999) candidates to try, in preference order, verified
# at runtime against the live CL_INDEX_TYPE / CL_COICOP_1999 codelists before
# use. ECPI has an empty list: the codelists genuinely contain no standalone
# energy-CPI code for this dataset (checked at runtime; see log_candidate
# entries in sources.md for the near-matches that were considered and
# rejected rather than substituted).
IMF_CANDIDATES = {
    "HCPI": [("CPI", "_T")],
    "FCPI": [("CPI", "CP01")],
    "CCPI": [("CCPI", "_T"), ("CCPIXFEN", "_T"), ("PCPIHACO", "_T")],
    "ECPI": [],
}
IMF_ECPI_REJECTED_NEAR_MATCHES = [
    ("CECO", None, "Commodity price index, energy, crude oil (petroleum) — a commodity "
                   "price index, not a consumer price index; wrong economic concept"),
    ("CPI", "CP04", "COICOP division 'Housing, water, electricity, gas and other fuels' — "
                     "mixes housing with energy, not an isolated energy CPI"),
    ("CPI", "CP07", "COICOP division 'Transport' — includes fuel but also vehicles, "
                     "transport services etc., not an isolated energy CPI"),
]


_imf_last_request_time = [0.0]
IMF_MIN_REQUEST_INTERVAL = 1.2  # seconds — observed empirically to avoid api.imf.org 503s


def imf_get_json(url: str, cache_key: str, params=None, force=False):
    cpath = cache_path("imf", cache_key, "json")
    if not force:
        cached = cache_read_json(cpath)
        if cached is not None:
            return cached, None
    # Be a polite client: api.imf.org returns intermittent 503s under rapid
    # back-to-back requests. A small fixed gap between live calls (cache hits
    # are exempt above) avoids most of them without slowing a normal run much.
    elapsed = time.monotonic() - _imf_last_request_time[0]
    if elapsed < IMF_MIN_REQUEST_INTERVAL:
        time.sleep(IMF_MIN_REQUEST_INTERVAL - elapsed)
    _imf_last_request_time[0] = time.monotonic()
    resp = http_get(url, params=params, headers={"Accept": "application/json"},
                     source=f"imf-{cache_key}", allow_statuses=(400,))
    if resp.status_code == 400:
        # Known live-API quirk: the JSON serializer throws a
        # JsonGenerationException when a fully-specified series key
        # resolves to zero published observations. Confirmed by
        # cross-checking the same query in the default XML format, which
        # returns HTTP 200 with an empty <DataSet/> (no <Series> element).
        # We treat this specific signature as "no data for this key", not
        # a transport failure.
        try:
            body = resp.json()
        except Exception:
            body = {}
        if "JsonGenerationException" in json.dumps(body):
            return None, "empty-result-400"
        resp.raise_for_status()
    resp.raise_for_status()
    data = resp.json()
    cache_write_json(cpath, data)
    return data, None


def imf_codelist_codes(codelist_id: str, force: bool) -> set[str]:
    try:
        data, _ = imf_get_json(f"{IMF_BASE}/codelist/IMF/{codelist_id}",
                                f"codelist_{codelist_id}", force=force)
        codes = data["data"]["codelists"][0]["codes"]
        return {c["id"] for c in codes}
    except Exception as exc:
        log.warning("IMF: could not fetch codelist %s (%s) — proceeding without verification", codelist_id, exc)
        return set()


def imf_parse_data_response(data: dict) -> tuple[dict, dict]:
    """Returns (date->value, series_attributes) for the first (only) series
    in an SDMX-JSON data response."""
    series = data["dataSets"][0].get("series", {})
    if not series:
        return {}, {}
    key = next(iter(series))
    s = series[key]
    time_values = data["structure"]["dimensions"]["observation"][0]["values"]
    date_values = {}
    for idx_str, obs in s["observations"].items():
        idx = int(idx_str)
        period_id = time_values[idx]["id"]  # e.g. "2024-M01" / "2024-Q1" / "2024"
        d = imf_period_to_date(period_id)
        val = obs[0]
        if val is None or val == "":
            continue
        date_values[d] = float(val)

    attrs_meta = data["structure"]["attributes"]["series"]
    attr_idx = s.get("attributes", [])
    attrs = {}
    for i, meta in enumerate(attrs_meta):
        if i >= len(attr_idx) or attr_idx[i] is None:
            continue
        values = meta.get("values")
        if values:
            attrs[meta["id"]] = values[attr_idx[i]]
    return date_values, attrs


def imf_period_to_date(period_id: str) -> date:
    if "-M" in period_id:
        y, m = period_id.split("-M")
        return date(int(y), int(m), 1)
    if "-Q" in period_id:
        y, q = period_id.split("-Q")
        return date(int(y), (int(q) - 1) * 3 + 1, 1)
    return date(int(period_id), 1, 1)


def imf_fetch_series(index: str, frequency: str, force: bool,
                      valid_index_types: set[str], valid_coicop: set[str]) -> SeriesResult:
    freq_code = IMF_FREQ_CODE[frequency]

    if index == "ECPI":
        for it, coicop, why in IMF_ECPI_REJECTED_NEAR_MATCHES:
            label = f"{it}" + (f".{coicop}" if coicop else "")
            log_candidate("imf", index, frequency, label, why, chosen=False,
                          reason="rejected: near-match, not substituted per no-substitution rule")
        note = ("IMF's CL_INDEX_TYPE and CL_COICOP_1999 codelists (dataset IMF.STA:CPI v5.0.0) "
                "contain no standalone energy-CPI code. Nearest candidates (commodity energy "
                "price index CECO, and COICOP division CP04 which mixes housing with energy) "
                "were considered and rejected — see sources.md.")
        log.info("IMF %s/%s: UNAVAILABLE — %s", index, frequency, note)
        return SeriesResult("imf", index, frequency, "MISSING", note=note)

    chosen_result = None
    for index_type, coicop in IMF_CANDIDATES[index]:
        label = f"{index_type}.{coicop}"
        if valid_index_types and index_type not in valid_index_types:
            log_candidate("imf", index, frequency, label, "", chosen=False,
                          reason=f"rejected: {index_type!r} not found in live CL_INDEX_TYPE codelist")
            continue
        if valid_coicop and coicop not in valid_coicop:
            log_candidate("imf", index, frequency, label, "", chosen=False,
                          reason=f"rejected: {coicop!r} not found in live CL_COICOP_1999 codelist")
            continue

        key = f"LKA.{index_type}.{coicop}.IX.{freq_code}"
        url = f"{IMF_BASE}/data/{IMF_DATAFLOW}/{key}"
        try:
            data, empty_flag = imf_get_json(url, f"data_{key}", force=force)
        except Exception as exc:
            log_candidate("imf", index, frequency, key, "", chosen=False,
                          reason=f"rejected: request failed ({exc})")
            FAILURES.append(f"IMF {index}/{frequency} candidate {key}: {exc}")
            continue

        if empty_flag or data is None:
            log_candidate("imf", index, frequency, key, "", chosen=False,
                          reason="rejected: key is valid but LKA has zero published observations")
            continue

        date_values, attrs = imf_parse_data_response(data)
        if not date_values:
            log_candidate("imf", index, frequency, key, "", chosen=False,
                          reason="rejected: response parsed but contained no observations")
            continue

        series_name = attrs.get("SERIES_NAME", {}).get("name") or \
            f"Sri Lanka — {data['structure'].get('name', 'Consumer Price Index')} — {label}"
        log_candidate("imf", index, frequency, key, series_name, chosen=True,
                      reason="chosen: first candidate (in preference order) with published LKA data")
        chosen_result = (key, date_values, attrs, series_name)
        break

    if chosen_result is None:
        note = (f"Tried {len(IMF_CANDIDATES[index])} candidate key(s) for {index}/{frequency}; "
                f"none had published Sri Lanka data. See sources.md candidate log.")
        log.info("IMF %s/%s: UNAVAILABLE — %s", index, frequency, note)
        return SeriesResult("imf", index, frequency, "MISSING", note=note)

    key, date_values, attrs, series_name = chosen_result
    df = build_series_df(frequency, date_values)
    required_end = REQUIRED_END[frequency]
    status = "OK" if df["date"].max() >= required_end else "SHORT"

    base_year = None
    ref = attrs.get("COMMON_REFERENCE_PERIOD", {}).get("id")
    if ref and ref.endswith("A"):
        base_year = ref[:-1]

    return SeriesResult(
        source="imf", index=index, frequency=frequency, status=status,
        series_id=key, title=series_name, units="Index", base_year=base_year,
        url=f"{IMF_BASE}/data/{IMF_DATAFLOW}/{key}",
        vintage="IMF.STA:CPI dataset version 5.0.0 (live SDMX 2.1 API, api.imf.org)",
        downloaded_at=utcnow_iso(), obs_count=int(df["value"].notna().sum()),
        first_date=df["date"].min(), last_date=df["date"].max(),
        gaps=find_gaps(df), base_year_breaks=detect_base_year_breaks(df, "index"),
        df=df, unit_type="index",
    )


# ===========================================================================
# World Bank Global Database of Inflation (downloadable workbook)
# ===========================================================================

WB_URL = "https://thedocs.worldbank.org/en/doc/1ad246272dbbc437c74323719506aa0c-0350012021/original/Inflation-data.xlsx"
WB_SHEET = {
    ("HCPI", "monthly"): "hcpi_m", ("HCPI", "quarterly"): "hcpi_q", ("HCPI", "annual"): "hcpi_a",
    ("FCPI", "monthly"): "fcpi_m", ("FCPI", "quarterly"): "fcpi_q", ("FCPI", "annual"): "fcpi_a",
    ("CCPI", "monthly"): "ccpi_m", ("CCPI", "quarterly"): "ccpi_q", ("CCPI", "annual"): "ccpi_a",
    ("ECPI", "monthly"): "ecpi_m", ("ECPI", "quarterly"): "ecpi_q", ("ECPI", "annual"): "ecpi_a",
}


def wb_download(force: bool) -> Path:
    path = RAW_DIR / "worldbank" / "Inflation-data.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return path
    resp = http_get(WB_URL, source="worldbank-download")
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path


def wb_version_string(xlsx_path: Path) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    ws = wb["Intro"]
    for row in ws.iter_rows(values_only=True):
        for cell in row:
            if isinstance(cell, str) and cell.strip().lower().startswith("version:"):
                wb.close()
                return cell.strip()
    wb.close()
    return "unknown (Version: line not found in Intro sheet)"


def wb_quarter_to_date(qcode: int) -> date:
    s = str(qcode)
    y, q = int(s[:4]), int(s[4:])
    return date(y, (q - 1) * 3 + 1, 1)


def wb_month_to_date(mcode: int) -> date:
    s = str(mcode)
    return date(int(s[:4]), int(s[4:6]), 1)


def wb_fetch_series(index: str, frequency: str, force: bool, xlsx_path: Path, version: str) -> SeriesResult:
    import openpyxl
    sheet_name = WB_SHEET[(index, frequency)]
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    if sheet_name not in wb.sheetnames:
        wb.close()
        note = f"Sheet {sheet_name!r} not found in workbook (sheets present: {wb.sheetnames})."
        return SeriesResult("worldbank", index, frequency, "ERROR", note=note)

    ws = wb[sheet_name]
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows))
    date_cols = [(i, h) for i, h in enumerate(header) if isinstance(h, int)]
    country_col = 0  # 'Country Code' is always the first column across sheets

    target_row = None
    for row in rows:
        if len(row) > country_col and row[country_col] == "LKA":
            target_row = row
            break
    wb.close()

    if target_row is None:
        note = f"'LKA' not found in Country Code column of sheet {sheet_name!r}."
        log.info("World Bank %s/%s: UNAVAILABLE — %s", index, frequency, note)
        return SeriesResult("worldbank", index, frequency, "MISSING", note=note)

    indicator_type_col = header.index("Indicator Type") if "Indicator Type" in header else None
    series_name_col = header.index("Series Name") if "Series Name" in header else None
    indicator_type = target_row[indicator_type_col] if indicator_type_col is not None else ""
    series_name = target_row[series_name_col] if series_name_col is not None else f"{index} ({frequency})"

    date_values = {}
    for i, h in date_cols:
        if i >= len(target_row) or target_row[i] is None:
            continue
        if frequency == "monthly":
            d = wb_month_to_date(h)
        elif frequency == "quarterly":
            d = wb_quarter_to_date(h)
        else:
            d = date(h, 1, 1)
        date_values[d] = float(target_row[i])

    if not date_values:
        note = f"Row for LKA found in {sheet_name!r} but every date column is empty."
        return SeriesResult("worldbank", index, frequency, "MISSING", note=note)

    unit_type = "yoy_pct" if str(indicator_type).lower() == "inflation" else "index"
    units = "Percent (year-on-year), as published" if unit_type == "yoy_pct" else "Index level (base year not stated per-series in workbook; see accompanying paper)"

    df = build_series_df(frequency, date_values)
    required_end = REQUIRED_END[frequency]
    status = "OK" if df["date"].max() >= required_end else "SHORT"

    log_candidate("worldbank", index, frequency, sheet_name, series_name, chosen=True,
                  reason="World Bank publishes exactly one series per index/frequency sheet "
                         "(no candidate selection needed) — row matched on Country Code == 'LKA'")

    return SeriesResult(
        source="worldbank", index=index, frequency=frequency, status=status,
        series_id=f"{sheet_name}:LKA", title=str(series_name), units=units, base_year=None,
        url="https://www.worldbank.org/en/research/brief/inflation-database",
        vintage=version, downloaded_at=utcnow_iso(),
        obs_count=int(df["value"].notna().sum()),
        first_date=df["date"].min(), last_date=df["date"].max(),
        gaps=find_gaps(df), base_year_breaks=detect_base_year_breaks(df, unit_type),
        df=df, unit_type=unit_type,
    )


# ===========================================================================
# Orchestration
# ===========================================================================

def output_path(source: str, index: str, frequency: str) -> Path:
    return DATA_DIR / f"{source}_{index}_{frequency}.csv"


def already_cached(source: str, index: str, frequency: str) -> bool:
    return output_path(source, index, frequency).exists()


def meta_sidecar_path(source: str, index: str, frequency: str) -> Path:
    d = RAW_DIR / "meta"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{source}_{index}_{frequency}.json"


def write_meta_sidecar(result: SeriesResult):
    """Persist the metadata fields a re-run can't recover from the plain
    date,value CSV alone (unit_type in particular — needed so the
    cross-source comparison still works after a --force-free re-run that
    skips re-fetching an already-cached series). Deliberately excludes
    derived analysis like base_year_breaks: that's recomputed fresh from
    the CSV every run so a heuristic change takes effect without --force."""
    meta = {
        "series_id": result.series_id, "title": result.title, "units": result.units,
        "base_year": result.base_year, "url": result.url, "vintage": result.vintage,
        "downloaded_at": result.downloaded_at, "unit_type": result.unit_type,
    }
    meta_sidecar_path(result.source, result.index, result.frequency).write_text(
        json.dumps(meta), encoding="utf-8")


def write_series_csv(result: SeriesResult):
    path = output_path(result.source, result.index, result.frequency)
    if result.df is None or result.df.empty:
        path.write_text("date,value\n", encoding="utf-8")
        return
    df = result.df.copy()
    df["date"] = df["date"].apply(lambda d: d.isoformat())
    df["value"] = df["value"].apply(lambda v: "" if pd.isna(v) else v)
    df.to_csv(path, index=False)


def run_fred(indices, frequencies, force) -> None:
    api_key = fred_api_key()
    for index in indices:
        for frequency in frequencies:
            combo_key = ("fred", index, frequency)
            if not force and already_cached("fred", index, frequency):
                log.info("FRED %s/%s: output CSV already exists, skipping (use --force to refetch)", index, frequency)
                continue
            log.info("FRED %s/%s: searching…", index, frequency)
            try:
                result = fred_fetch_series(index, frequency, api_key, force)
            except Exception as exc:
                log.error("FRED %s/%s: unexpected error: %s", index, frequency, exc)
                FAILURES.append(f"FRED {index}/{frequency}: {exc}")
                result = SeriesResult("fred", index, frequency, "ERROR", note=str(exc))
            RESULTS[combo_key] = result
            if result.df is not None:
                write_series_csv(result)
                if result.df is not None and not result.df.empty:
                    write_meta_sidecar(result)


def run_imf(indices, frequencies, force) -> None:
    log.info("IMF: fetching codelists for runtime verification…")
    valid_index_types = imf_codelist_codes("CL_INDEX_TYPE", force)
    valid_coicop = imf_codelist_codes("CL_COICOP_1999", force)
    valid_countries = imf_codelist_codes("CL_COUNTRY", force)
    if valid_countries and "LKA" not in valid_countries:
        log.error("IMF: 'LKA' not found in live CL_COUNTRY codelist — aborting IMF fetch")
        FAILURES.append("IMF: LKA missing from CL_COUNTRY codelist")
        return

    for index in indices:
        for frequency in frequencies:
            combo_key = ("imf", index, frequency)
            if not force and already_cached("imf", index, frequency):
                log.info("IMF %s/%s: output CSV already exists, skipping (use --force to refetch)", index, frequency)
                continue
            log.info("IMF %s/%s: querying…", index, frequency)
            try:
                result = imf_fetch_series(index, frequency, force, valid_index_types, valid_coicop)
            except Exception as exc:
                log.error("IMF %s/%s: unexpected error: %s", index, frequency, exc)
                FAILURES.append(f"IMF {index}/{frequency}: {exc}")
                result = SeriesResult("imf", index, frequency, "ERROR", note=str(exc))
            RESULTS[combo_key] = result
            if result.df is not None:
                write_series_csv(result)
                if result.df is not None and not result.df.empty:
                    write_meta_sidecar(result)


def run_worldbank(indices, frequencies, force) -> None:
    log.info("World Bank: downloading Global Database of Inflation workbook…")
    try:
        xlsx_path = wb_download(force)
        version = wb_version_string(xlsx_path)
        log.info("World Bank: workbook version = %r", version)
    except Exception as exc:
        log.error("World Bank: failed to download/open workbook: %s", exc)
        FAILURES.append(f"World Bank: download/open failed: {exc}")
        return

    for index in indices:
        for frequency in frequencies:
            combo_key = ("worldbank", index, frequency)
            if not force and already_cached("worldbank", index, frequency):
                log.info("World Bank %s/%s: output CSV already exists, skipping (use --force to refetch)", index, frequency)
                continue
            log.info("World Bank %s/%s: extracting…", index, frequency)
            try:
                result = wb_fetch_series(index, frequency, force, xlsx_path, version)
            except Exception as exc:
                log.error("World Bank %s/%s: unexpected error: %s", index, frequency, exc)
                FAILURES.append(f"World Bank {index}/{frequency}: {exc}")
                result = SeriesResult("worldbank", index, frequency, "ERROR", note=str(exc))
            RESULTS[combo_key] = result
            if result.df is not None:
                write_series_csv(result)
                if result.df is not None and not result.df.empty:
                    write_meta_sidecar(result)


# ---------------------------------------------------------------------------
# Reading back already-cached CSVs so reports stay complete across runs
# ---------------------------------------------------------------------------

def load_existing_results(sources, indices, frequencies):
    """For combos skipped this run (CSV already present), load them back
    into RESULTS with minimal metadata so sources.md/coverage_report.md
    still cover the full requested matrix, not just what was freshly
    fetched. Full metadata (title, units, etc.) is only available for
    combos actually fetched this run or in a prior run's raw cache."""
    for source in sources:
        for index in indices:
            for frequency in frequencies:
                combo_key = (source, index, frequency)
                if combo_key in RESULTS:
                    continue
                path = output_path(source, index, frequency)
                if not path.exists():
                    continue
                df = pd.read_csv(path, dtype={"value": "object"})
                if df.empty:
                    RESULTS[combo_key] = SeriesResult(source, index, frequency, "MISSING",
                                                       note="cached empty output from a prior run")
                    continue
                df["date"] = pd.to_datetime(df["date"]).dt.date
                df["value"] = pd.to_numeric(df["value"], errors="coerce")
                required_end = REQUIRED_END[frequency]
                status = "OK" if df["date"].max() >= required_end else "SHORT"

                meta = {}
                meta_path = meta_sidecar_path(source, index, frequency)
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    except Exception:
                        meta = {}

                RESULTS[combo_key] = SeriesResult(
                    source=source, index=index, frequency=frequency, status=status,
                    series_id=meta.get("series_id"), title=meta.get("title"),
                    units=meta.get("units"), base_year=meta.get("base_year"),
                    url=meta.get("url"), vintage=meta.get("vintage"),
                    downloaded_at=meta.get("downloaded_at"),
                    unit_type=meta.get("unit_type"),
                    base_year_breaks=detect_base_year_breaks(df, meta.get("unit_type")),
                    note="loaded from previously cached output CSV (not refetched this run)"
                         + ("" if meta else " — no metadata sidecar found, so sources.md entry "
                                             "and cross-source comparison for this series will "
                                             "be incomplete; re-run with --force to regenerate it"),
                    obs_count=int(df["value"].notna().sum()),
                    first_date=df["date"].min(), last_date=df["date"].max(),
                    gaps=find_gaps(df), df=df,
                )


# ===========================================================================
# Reports
# ===========================================================================

def write_sources_md(sources, indices, frequencies):
    lines = ["# Data sources\n",
             f"Generated {utcnow_iso()} by `fetch_data.py`. One entry per attempted series.\n"]

    for source in sources:
        lines.append(f"\n## {source}\n")
        for index in indices:
            for frequency in frequencies:
                r = RESULTS.get((source, index, frequency))
                if r is None:
                    continue
                lines.append(f"\n### {index} / {frequency}\n")
                if r.status in ("OK", "SHORT"):
                    lines.append(f"- **Series ID / indicator code:** `{r.series_id}`")
                    lines.append(f"- **Official title:** {r.title}")
                    lines.append(f"- **Units:** {r.units}")
                    lines.append(f"- **Base year:** {r.base_year or 'n/a'}")
                    lines.append(f"- **Source URL:** {r.url}")
                    lines.append(f"- **Vintage / database version:** {r.vintage}")
                    lines.append(f"- **Downloaded (UTC):** {r.downloaded_at}")
                    if r.status == "SHORT":
                        lines.append(f"- **⚠ SHORT:** last observation {r.last_date} is before the "
                                      f"required {REQUIRED_END_LABEL[frequency]}")
                else:
                    lines.append(f"- **Status:** {r.status}")
                    lines.append(f"- **Evidence:** {r.note}")

        lines.append(f"\n#### Candidates considered — {source}\n")
        cand_rows = [c for c in CANDIDATES_LOG if c.source == source]
        if not cand_rows:
            lines.append("(no candidate search logged for this source)")
        else:
            lines.append("| Index | Frequency | Identifier | Title | Chosen | Reason |")
            lines.append("|---|---|---|---|---|---|")
            for c in cand_rows:
                lines.append(f"| {c.index} | {c.frequency} | `{c.identifier}` | {c.title[:80]} | "
                              f"{'YES' if c.chosen else 'no'} | {c.reason} |")

    (DATA_DIR / "sources.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Wrote sources.md")


def write_coverage_report(sources, indices, frequencies):
    lines = ["# Coverage report\n",
             f"Generated {utcnow_iso()} by `fetch_data.py`.\n",
             "Required end points: monthly through Aug 2026, quarterly through Q2 2026, "
             "annual through 2025.\n"]

    lines.append("\n| Source | Index | Freq | Status | First date | Last date | Obs | Gaps | Base-year breaks |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    short_or_missing = []
    for source in sources:
        for index in indices:
            for frequency in frequencies:
                r = RESULTS.get((source, index, frequency))
                if r is None:
                    continue
                first = r.first_date.isoformat() if r.first_date else "—"
                last = r.last_date.isoformat() if r.last_date else "—"
                gap_n = len(r.gaps)
                break_n = len(r.base_year_breaks)
                lines.append(f"| {source} | {index} | {frequency} | {r.status} | {first} | {last} | "
                              f"{r.obs_count} | {gap_n} | {break_n} |")
                if r.status in ("SHORT", "MISSING", "ERROR"):
                    short_or_missing.append((source, index, frequency, r))

    lines.append("\n## Flagged series\n")
    if not short_or_missing:
        lines.append("None — every requested series met its required end point.")
    else:
        for source, index, frequency, r in short_or_missing:
            lines.append(f"\n### {source} {index} {frequency} — {r.status}")
            if r.status == "SHORT":
                lines.append(f"Last observation is **{r.last_date}**, required "
                              f"**{REQUIRED_END_LABEL[frequency]}**. {r.note}")
            else:
                lines.append(r.note or "(no further detail)")

    lines.append("\n## Gap detail\n")
    any_gaps = False
    for source in sources:
        for index in indices:
            for frequency in frequencies:
                r = RESULTS.get((source, index, frequency))
                if r is None or not r.gaps:
                    continue
                any_gaps = True
                lines.append(f"- **{source} {index} {frequency}**: {len(r.gaps)} gap(s) at "
                              f"{', '.join(r.gaps[:20])}{' …' if len(r.gaps) > 20 else ''}")
    if not any_gaps:
        lines.append("No internal gaps detected in any series.")

    lines.append("\n## Suspected base-year breaks (heuristic: a >20% single-period drop, or a jump "
                 "that lands within 5 points of 100, in an index-level series — a plain magnitude "
                 "threshold would misfire on Sri Lanka's genuine ~50% YoY inflation in 2022, so this "
                 "only flags rebase-shaped jumps: steep drops or resets near the conventional 100 base)\n")
    any_breaks = False
    for source in sources:
        for index in indices:
            for frequency in frequencies:
                r = RESULTS.get((source, index, frequency))
                if r is None or not r.base_year_breaks:
                    continue
                any_breaks = True
                lines.append(f"- **{source} {index} {frequency}**: possible break at "
                              f"{', '.join(r.base_year_breaks)} — verify against publisher rebasing notes "
                              f"before treating as a real price movement.")
    if not any_breaks:
        lines.append("No candidate breaks flagged.")

    (DATA_DIR / "coverage_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Wrote coverage_report.md")


# ---------------------------------------------------------------------------
# Cross-source comparison
# ---------------------------------------------------------------------------

def to_yoy_pct(r: SeriesResult) -> Optional[pd.Series]:
    if r.df is None or r.df.empty or r.unit_type is None:
        return None
    s = r.df.set_index("date")["value"].astype(float)
    if r.unit_type == "yoy_pct":
        return s
    periods = {"monthly": 12, "quarterly": 4, "annual": 1}[r.frequency]
    return s.pct_change(periods=periods) * 100.0


def spearman(a: pd.Series, b: pd.Series) -> Optional[float]:
    paired = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(paired) < 3:
        return None
    return paired.iloc[:, 0].rank().corr(paired.iloc[:, 1].rank())


def write_source_comparison(sources, indices, frequencies):
    md = ["# Source comparison\n",
          f"Generated {utcnow_iso()} by `fetch_data.py`.\n",
          "All series normalised to year-on-year percent change before comparison "
          "(index-level series converted via period-over-period-a-year-ago percent "
          "change; series already published as YoY percent are used as-is). This "
          "normalisation is for comparison only — the saved CSVs keep each source's "
          "as-published units unconverted.\n"]
    csv_rows = []

    for index in indices:
        for frequency in frequencies:
            available = {}
            for source in sources:
                r = RESULTS.get((source, index, frequency))
                if r is None or r.df is None or r.df.empty:
                    continue
                yoy = to_yoy_pct(r)
                if yoy is not None and yoy.notna().any():
                    available[source] = (r, yoy)

            md.append(f"\n## {index} / {frequency}\n")
            if len(available) == 0:
                md.append("No source has usable data for this index/frequency.")
                continue
            md.append("**Coverage:**\n")
            md.append("| Source | First date | Last date |")
            md.append("|---|---|---|")
            for source, (r, yoy) in available.items():
                md.append(f"| {source} | {r.first_date} | {r.last_date} |")

            if len(available) < 2:
                only = next(iter(available))
                md.append(f"\nOnly one source (`{only}`) publishes this index/frequency combination — "
                          f"no cross-source comparison is possible. This is a coverage finding in its "
                          f"own right (see coverage_report.md).")
                continue

            pairs = []
            names = list(available.keys())
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    a_name, b_name = names[i], names[j]
                    a_series = available[a_name][1]
                    b_series = available[b_name][1]
                    joined = pd.concat([a_series, b_series], axis=1, join="inner",
                                        keys=[a_name, b_name]).dropna()
                    if joined.empty:
                        md.append(f"\n`{a_name}` vs `{b_name}`: no overlapping dates after normalisation.")
                        continue
                    diff = (joined[a_name] - joined[b_name]).abs()
                    mean_diff = diff.mean()
                    max_diff = diff.max()
                    rho = spearman(joined[a_name], joined[b_name])
                    big_diff_dates = diff[diff > 0.1]
                    in_eval_window = [(d, v) for d, v in big_diff_dates.items()
                                       if date(2020, 1, 1) <= d <= date(2026, 12, 31)]

                    md.append(f"\n**`{a_name}` vs `{b_name}`** (overlap {joined.index.min()} "
                              f"→ {joined.index.max()}, n={len(joined)})")
                    md.append(f"- mean |diff| = {mean_diff:.3f}pp, max |diff| = {max_diff:.3f}pp")
                    md.append(f"- rank correlation (Spearman) = {rho:.4f}" if rho is not None
                              else "- rank correlation: not enough overlap to compute")
                    md.append(f"- dates differing by >0.1pp: {len(big_diff_dates)} "
                              f"({len(in_eval_window)} of those fall in the 2020-2026 evaluation window)")
                    if len(big_diff_dates) > 0:
                        sample = list(big_diff_dates.items())[:15]
                        md.append("  " + "; ".join(f"{d}: {v:.2f}pp" for d, v in sample) +
                                  (" …" if len(big_diff_dates) > 15 else ""))

                    for d, v in big_diff_dates.items():
                        csv_rows.append({
                            "index": index, "frequency": frequency,
                            "source_a": a_name, "source_b": b_name,
                            "date": d.isoformat(),
                            "value_a": joined.loc[d, a_name], "value_b": joined.loc[d, b_name],
                            "abs_diff_pp": v,
                            "in_2020_2026_window": date(2020, 1, 1) <= d <= date(2026, 12, 31),
                        })
                    pairs.append((a_name, b_name, mean_diff, max_diff, rho, len(in_eval_window)))

            md.append("\n**Verdict:** ")
            if not pairs:
                md.append("No overlapping data between any pair of sources for this combination.")
            else:
                worst = max(pairs, key=lambda p: p[3])
                crisis_flag = worst[5] > 0
                agree = worst[3] <= 0.5
                verdict = []
                if agree:
                    verdict.append(f"Sources broadly agree (worst pairwise max diff "
                                    f"{worst[3]:.2f}pp, {worst[0]} vs {worst[1]}).")
                else:
                    verdict.append(f"Sources diverge meaningfully at times (worst pairwise max diff "
                                    f"{worst[3]:.2f}pp, {worst[0]} vs {worst[1]}).")
                if crisis_flag:
                    verdict.append(f"{worst[5]} of the >0.1pp divergence dates fall inside the "
                                    f"2020-2026 evaluation window — this matters more than agreement "
                                    f"or disagreement outside it (pre-2020 divergence is much lower "
                                    f"stakes for this study).")
                else:
                    verdict.append("None of the notable divergence dates fall inside the 2020-2026 "
                                    "evaluation window.")
                md.append(" ".join(verdict))

    (DATA_DIR / "source_comparison.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if csv_rows:
        pd.DataFrame(csv_rows).to_csv(DATA_DIR / "source_comparison.csv", index=False)
    else:
        (DATA_DIR / "source_comparison.csv").write_text(
            "index,frequency,source_a,source_b,date,value_a,value_b,abs_diff_pp,in_2020_2026_window\n",
            encoding="utf-8")
    log.info("Wrote source_comparison.md and source_comparison.csv")


# ---------------------------------------------------------------------------
# Summary table + exit status
# ---------------------------------------------------------------------------

def print_summary(sources, indices, frequencies) -> int:
    rows = []
    for source in sources:
        for index in indices:
            for frequency in frequencies:
                r = RESULTS.get((source, index, frequency))
                if r is None:
                    continue
                first = r.first_date.isoformat() if r.first_date else "—"
                last = r.last_date.isoformat() if r.last_date else "—"
                rows.append((source, index, frequency, r.obs_count, first, last, r.status))

    header = f"{'source':<10} {'index':<6} {'freq':<10} {'obs':>5}  {'first':<12} {'last':<12}  status"
    print("\n" + header)
    print("-" * len(header))
    for row in rows:
        print(f"{row[0]:<10} {row[1]:<6} {row[2]:<10} {row[3]:>5}  {row[4]:<12} {row[5]:<12}  {row[6]}")

    n_short = sum(1 for r in rows if r[6] == "SHORT")
    n_missing = sum(1 for r in rows if r[6] == "MISSING")
    n_error = sum(1 for r in rows if r[6] == "ERROR")
    n_ok = sum(1 for r in rows if r[6] == "OK")
    print(f"\n{n_ok} OK, {n_short} SHORT, {n_missing} MISSING, {n_error} ERROR (of {len(rows)} requested combinations)")

    if FAILURES:
        print("\n" + "=" * 70)
        print("FAILURES DURING THIS RUN:")
        for f in FAILURES:
            print(f"  - {f}")
        print("=" * 70)

    loud_fail = False
    short_rows = [r for r in rows if r[6] == "SHORT"]
    if short_rows:
        loud_fail = True
        print("\n" + "!" * 70)
        print("! REQUIRED END-DATE SHORTFALL — the experiment plan needs data through")
        print("! monthly=Aug2026, quarterly=Q2 2026, annual=2025. The following series")
        print("! do NOT reach that point and must not be used for the final rolling")
        print("! origin without checking for a newer source:")
        for r in short_rows:
            print(f"!   {r[0]} {r[1]} {r[2]}: last observation {r[5]} (required {REQUIRED_END_LABEL[r[2]]})")
        print("!" * 70)

    if n_error > 0:
        loud_fail = True

    return 1 if loud_fail else 0


# ===========================================================================
# CLI
# ===========================================================================

def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", choices=SOURCES + ["all"], default="all")
    p.add_argument("--index", choices=INDICES + ["all"], default="all")
    p.add_argument("--frequency", choices=FREQUENCIES + ["all"], default="all")
    p.add_argument("--force", action="store_true", help="bypass raw cache and re-fetch everything")
    return p.parse_args()


def main():
    args = parse_args()
    sources = SOURCES if args.source == "all" else [args.source]
    indices = INDICES if args.index == "all" else [args.index]
    frequencies = FREQUENCIES if args.frequency == "all" else [args.frequency]

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if "fred" in sources:
        run_fred(indices, frequencies, args.force)
    if "imf" in sources:
        run_imf(indices, frequencies, args.force)
    if "worldbank" in sources:
        run_worldbank(indices, frequencies, args.force)

    # Reports should reflect the full requested matrix, including combos
    # skipped this run because their CSV was already cached.
    load_existing_results(sources, indices, frequencies)

    write_sources_md(sources, indices, frequencies)
    write_coverage_report(sources, indices, frequencies)
    write_source_comparison(sources, indices, frequencies)

    exit_code = print_summary(sources, indices, frequencies)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
