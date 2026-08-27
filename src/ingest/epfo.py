"""Parse EPFO payroll releases into a tidy monthly panel.

Releases are cumulative and revised: each EPFO "Provisional Estimate of Net
Payroll" PDF carries monthly detail ONLY for its current fiscal year (earlier
years collapse to FY aggregates), with a two-month data lag. The latest release
therefore does NOT contain the full monthly back-series; the panel is stitched
from the last release that reports each fiscal year monthly (normally the May
release of the following FY). During Mar-May 2024 EPFO issued single-month
releases, so FY2023-24 needs four files. Monthly data before Apr-2020 exists
only in MoSPI "Payroll Reporting in India" releases (gender x age x
{new, ceased, rejoined}; no net-payroll column). Known-unrecoverable months:
Feb-Mar 2019 and Nov 2019 - Mar 2020 (see data/raw/epfo/NOTES.md).

Per-release table anatomy (uniform across EPFO releases):
  page 1        month x age-band net payroll (used as a cross-check)
  section 2     per-month age x (a new, b exited, c rejoined, d net payroll)
  section 3     same but exits restricted to post-Sep-2017 joiners -> skipped
  state pages   one page per age bucket, state x (FY cols + monthly cols), net
  industry      two age buckets per page, top-10 industries x cols, net
  gender pages  per-month age x {new, ceased, rejoined} x gender

Raw PDFs are read-only inputs; output goes to data/processed/ (Golden Rule 6).
Values that resist parsing are logged to logs/epfo_parse_issues.csv, never
guessed (Golden Rule 1).
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import polars as pl

from atlas_common import logs_dir, processed_dir, raw_dir
from atlas_common.schemas import epfo_payroll

# Last release reporting each block of data months at monthly frequency.
# (filename, source_release, first_month, last_month) -- ranges must not overlap.
EPFO_SOURCES = [
    ("epfo_May-2021-1.pdf", "epfo_2021-05", "2020-04", "2021-03"),
    ("epfo_May-2022.pdf", "epfo_2022-05", "2021-04", "2022-03"),
    ("epfo_May-2023.pdf", "epfo_2023-05", "2022-04", "2023-03"),
    ("epfo_February-2024.pdf", "epfo_2024-02", "2023-04", "2023-12"),
    ("epfo_March-2024.pdf", "epfo_2024-03", "2024-01", "2024-01"),
    ("epfo_April-2024.pdf", "epfo_2024-04", "2024-02", "2024-02"),
    ("epfo_May-2024.pdf", "epfo_2024-05", "2024-03", "2024-03"),
    ("epfo_May-2025.pdf", "epfo_2025-05", "2024-04", "2025-03"),
    ("epfo_September-2025.pdf", "epfo_2025-09", "2025-04", "2025-07"),
]

# MoSPI fallback for the pre-EPFO-format era (monthly gender x age tables).
MOSPI_TEXT_SOURCE = (
    "mospi_Payroll_Reporting_in_India_-_An_Employment_Perspective_-_January_2019_250319_Release_.pdf",
    "mospi_2019-03",
    "2017-09",
    "2019-01",
    (0, 4),  # EPF section on pages 1-4; ESI/NPS follow
)
MOSPI_TABLE_SOURCE = (
    "mospi_Rev-Press_Release_Payroll_Reporting_in_India_-_for_24_December'19.pdf",
    "mospi_2019-12",
    "2019-04",
    "2019-10",
    (1, 3),  # EPF monthly tables on pages 2-3
)

AGE_BANDS = ["<18", "18-21", "22-25", "26-28", "29-35", ">35"]
_BAND_MAP = {
    "less than 18": "<18",
    "<18": "<18",
    "18-21": "18-21",
    "22-25": "22-25",
    "26-28": "26-28",
    "29-35": "29-35",
    "more than 35": ">35",
    ">35": ">35",
}
_GENDER_MAP = {
    "male": "male",
    "female": "female",
    "transgender": "transgender",
    # MoSPI releases label the same column "Others"; documented in NOTES.md
    "others": "transgender",
    "notavailable": "not_available",
    "total": "total",
}
MEASURES_GENDER = ["new_subscribers", "ceased", "rejoined"]

_MONTHS = {
    m.lower(): i + 1
    for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"]
    )
}
_MONTHS["sepember"] = 9  # typo in the Mar-2019 MoSPI release ("Sepember 2018")
_ABBR = {m[:3].lower(): i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

FULL_MONTH_RE = re.compile(r"^([A-Za-z]+)[ ,]+(20\d\d)$")
ABBR_MONTH_RE = re.compile(r"^([A-Z][a-z]{2})-(\d{2}|20\d\d)$")
FY_LABEL_RE = re.compile(r"^20\d\d-\d\d\b")
VALUE_RE = re.compile(r"^-?\d+$")

DATA_MONTH_MIN, DATA_MONTH_MAX = "2017-09", "2026-12"

# Documented header typos in the raw PDFs (see data/raw/epfo/NOTES.md).
# epfo_May-2021-1: several state/industry pages head the Apr-2020 column
# 'Apr-19' (the <18 state page and the value sequence -- COVID negatives,
# then May-20, Jun-20 ... -- pin it as Apr-2020).
HEADER_FIXES = {("epfo_2021-05", "Apr-19"): "2020-04"}

# Canonicalise industry-head spellings that vary across releases (some PDFs
# truncate the longest head mid-word).
INDUSTRY_FIXES = {
    "ESTABLISHMENT ENGAGED IN MANUFACTURE, MARKETING SERVICING, USAGE OF COMP":
        "ESTABLISHMENT ENGAGED IN MANUFACTURE, MARKETING SERVICING, USAGE OF COMPUTERS",
}
# Pre-EPFO-format segment (MoSPI vintage, no net-payroll measure, holes at
# 2019-02/03); flagged so analysis dummies it out rather than splicing.
SERIES_BREAK_BEFORE = "2020-04"


def _clean(cell: str | None) -> str:
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


def _parse_value(tok: str) -> int | None:
    tok = tok.replace(",", "").replace(" ", "").strip()
    if tok in {"-", "–"}:
        return 0  # nil marker in MoSPI tables (validated against row totals)
    if VALUE_RE.match(tok):
        return int(tok)
    return None


def _band(cell: str) -> str | None:
    """Normalise 'Less than 18', 'B - 18 - 21', 'F - >35' etc. to an age band."""
    c = _clean(cell)
    c = re.sub(r"^[A-F]\s*-\s*", "", c)  # gender-table prefix 'A - '
    c = re.sub(r"\s*-\s*", "-", c).lower()
    return _BAND_MAP.get(c)


def _full_month(cell: str) -> str | None:
    m = FULL_MONTH_RE.match(_clean(cell))
    if not m or m.group(1).lower() not in _MONTHS:
        return None
    return f"{m.group(2)}-{_MONTHS[m.group(1).lower()]:02d}"


def _abbr_month(cell: str) -> str | None:
    m = ABBR_MONTH_RE.match(_clean(cell))
    if not m or m.group(1).lower() not in _ABBR:
        return None
    year = m.group(2) if len(m.group(2)) == 4 else "20" + m.group(2)
    ym = f"{year}-{_ABBR[m.group(1).lower()]:02d}"
    # guards against header glitches like 'Sep-05' (a mangled '2024-25' FY cell)
    return ym if DATA_MONTH_MIN <= ym <= DATA_MONTH_MAX else None


def _measure_of(header: str) -> str | None:
    h = header.lower()
    if "rejoined" in h:
        return "rejoined"
    if "ceased" in h or "exited" in h:
        return "ceased"
    if "new epf" in h:
        return "new_subscribers"
    return None  # e.g. ESI/NPS 'existing employees' tables


class IssueLog:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, source: str, page: int, context: str, detail: str) -> None:
        self.rows.append(
            {"source": source, "page": page, "context": context, "detail": detail}
        )

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["source", "page", "context", "detail"])
            w.writeheader()
            w.writerows(self.rows)


def parse_epfo_pdf(
    path: Path,
    release: str,
    issues: IssueLog,
    pages: tuple[int, int] | None = None,
    national_from_gender_total: bool = False,
) -> tuple[list[dict], dict]:
    """Walk one EPFO-format PDF's tables; return (rows, page1 net cross-check).

    A single row-state machine handles every section because each block carries
    its own label/header rows: a period label ('April 2025' / '2018-19') applies
    to the next block; 'Age'/'Age Slab' headers open flow or gender blocks
    (variant detected from the sub-header); 'State'/'Industry' headers carry
    their data months in the columns. FY-labelled blocks are skipped (period
    None); section-3 blocks ('joined in or after Sep-2017') are skipped.
    """
    rows: list[dict] = []
    page1: dict[tuple[str, str], int] = {}
    mode: str | None = None
    period: str | None = None
    bucket: str | None = None
    group_header: list[str] | None = None
    gender_cols: list[tuple[int, str, str]] = []  # (col, gender, measure)
    gender_total_cols: list[tuple[int, str]] = []  # (col, measure)
    gender_seen: set[str] = set()  # bands emitted in the current gender block
    gender_orphans: list[tuple[int, dict, dict]] = []  # rows with garbled band label
    month_cols: list[tuple[int, str]] = []  # state/industry: (col, data_month)
    page1_cols: list[tuple[int, str]] = []

    def emit_gender_row(band, parsed, totals):
        for (g, m), v in parsed.items():
            emit(m, band, v, gender=g)
        if national_from_gender_total:
            for m, v in totals.items():
                emit(m, band, v)

    def flush_gender_block():
        """Resolve rows whose age-band label failed glyph extraction: if the
        block is missing exactly one band and holds exactly one valid orphan
        row, the assignment is forced (and row-sum validated); else drop+log."""
        nonlocal gender_seen, gender_orphans
        missing = [b for b in AGE_BANDS if b not in gender_seen]
        if len(gender_orphans) == 1 and len(missing) == 1 and period is not None:
            opno, parsed, totals = gender_orphans[0]
            emit_gender_row(missing[0], parsed, totals)
            issues.add(release, opno, f"gender {period} {missing[0]}",
                       "band label garbled in PDF; assigned as the block's "
                       "only missing band (row-sums validated)")
        elif gender_orphans:
            for opno, parsed, totals in gender_orphans:
                issues.add(release, opno, f"gender {period}",
                           f"dropped unassignable row (missing bands: {missing})")
        gender_seen, gender_orphans = set(), []

    def emit(measure, band, value, gender=None, industry=None, state=None, month=None):
        rows.append(
            {
                "data_month": month or period,
                "source_release": release,
                "measure": measure,
                "age_band": band,
                "gender": gender,
                "industry": industry,
                "state": state,
                "value": value,
            }
        )

    with pdfplumber.open(path) as pdf:
        page_iter = pdf.pages if pages is None else pdf.pages[pages[0] : pages[1]]
        for page in page_iter:
            pno = page.page_number
            for table in page.extract_tables():
                for raw in table:
                    cells = [_clean(c) for c in raw]
                    c0 = cells[0]
                    rest_empty = all(not c for c in cells[1:])

                    # sub-header resolution for a just-seen Age/Age Slab header
                    if group_header is not None:
                        genders = [
                            _GENDER_MAP.get(re.sub(r"[\s-]", "", c).lower())
                            for c in cells
                        ]
                        if "male" in genders:
                            measures = [
                                m for c in group_header[1:] if (m := _measure_of(c))
                            ]
                            idx = [
                                (i, g) for i, g in enumerate(genders) if g is not None
                            ]
                            group_seq = ["male", "female", "transgender",
                                         "not_available", "total"] * 3
                            if measures != MEASURES_GENDER:
                                issues.add(release, pno, "gender-header",
                                           f"unrecognised measures: {group_header}")
                                mode = "skip"
                            elif len(idx) != 15 and len(cells) in (16, 18):
                                # sub-header garbled by interleaved rotated text
                                # (e.g. Oct-2019 block in the Dec-2019 MoSPI
                                # release); columns positions are fixed per
                                # layout, so fall back to the positional
                                # template iff every cell that DID parse agrees
                                template = (
                                    list(range(1, 16)) if len(cells) == 16
                                    else [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17]
                                )
                                expected = dict(zip(template, group_seq))
                                if all(expected.get(i) == g for i, g in idx):
                                    idx = list(zip(template, group_seq))
                                    issues.add(release, pno, "gender-header",
                                               "positional fallback applied "
                                               f"(garbled sub-header: {cells})")
                                else:
                                    issues.add(release, pno, "gender-header",
                                               f"unrecognised layout: {cells}")
                                    idx = []
                                    mode = "skip"
                            elif len(idx) != 15:
                                issues.add(release, pno, "gender-header",
                                           f"unrecognised layout: {cells}")
                                idx = []
                                mode = "skip"
                            if len(idx) == 15:
                                gender_cols, gender_total_cols = [], []
                                for gi, (col, g) in enumerate(idx):
                                    measure = measures[gi // 5]
                                    if g == "total":
                                        gender_total_cols.append((col, measure))
                                    else:
                                        gender_cols.append((col, g, measure))
                                mode = "gender"
                            group_header = None
                            continue
                        if "(a)" in cells or "(d)" in cells:
                            mode = "flow"
                            group_header = None
                            continue
                        if not any(cells):
                            continue
                        # fall through: re-classify this row (e.g. band row)
                        mode = "flow"
                        group_header = None

                    # period labels (apply to the following block)
                    if rest_empty and c0:
                        if (ym := _full_month(c0)) is not None:
                            flush_gender_block()
                            period = ym
                            continue
                        if FY_LABEL_RE.match(c0) or "from sep" in c0.lower().replace("(", ""):
                            flush_gender_block()
                            period = None  # FY aggregate block: skip
                            continue
                        if c0.startswith("Age Bucket"):
                            bucket = _band(c0.split(":", 1)[1])
                            continue

                    # section headers
                    if "Month/Age" in c0:
                        mode = "page1"
                        page1_cols = [
                            (i, b) for i, c in enumerate(cells[1:], 1)
                            if (b := _band(c)) is not None
                        ]
                        continue
                    if c0 in ("State", "Industry"):
                        mode = c0.lower()
                        month_cols = []
                        for i, c in enumerate(cells[1:], 1):
                            if (release, c) in HEADER_FIXES:
                                issues.add(release, pno, f"{mode}-header",
                                           f"applied documented fix {c!r} -> "
                                           f"{HEADER_FIXES[(release, c)]}")
                                month_cols.append((i, HEADER_FIXES[(release, c)]))
                            elif (ym := _abbr_month(c)) is not None:
                                month_cols.append((i, ym))
                        continue
                    if c0 in ("Age", "Age Slab") or re.match(r"^Age\b", c0):
                        joined = " ".join(cells).lower()
                        if "joined in or after" in joined or "net new epf" in joined:
                            mode = "skip"  # section-3 variant
                        else:
                            group_header = cells  # variant known at sub-header
                        continue

                    band = _band(c0)

                    if mode == "flow" and band:
                        if period is None:
                            continue  # FY aggregate block
                        vals = [_parse_value(c) for c in cells[1:5]]
                        if len([v for v in vals if v is not None]) != 4:
                            issues.add(release, pno, f"flow {period} {band}",
                                       f"unparseable cells: {cells[1:5]}")
                            continue
                        a, b, c, d = vals
                        if a - b + c != d:
                            issues.add(release, pno, f"flow {period} {band}",
                                       f"identity a-b+c!=d: {vals}")
                        for measure, v in zip(
                            ["new_subscribers", "ceased", "rejoined", "net_payroll"], vals
                        ):
                            emit(measure, band, v)
                        continue

                    if mode == "gender" and (band or c0):
                        if period is None or "TOTAL" in c0.upper():
                            continue
                        parsed = {
                            (g, m): _parse_value(cells[col]) if col < len(cells) else None
                            for col, g, m in gender_cols
                        }
                        totals = {
                            m: _parse_value(cells[col]) if col < len(cells) else None
                            for col, m in gender_total_cols
                        }
                        bad = False
                        for m in MEASURES_GENDER:
                            mv = [parsed[(g, m)] for g in
                                  ["male", "female", "transgender", "not_available"]]
                            if None in mv or totals[m] is None or sum(mv) != totals[m]:
                                if band:  # garbled non-band rows are just noise
                                    issues.add(release, pno, f"gender {period} {band} {m}",
                                               f"row-sum mismatch or unparseable: {mv} vs {totals[m]}")
                                bad = True
                        if bad:
                            continue
                        if band is None:
                            # valid values but garbled band label; hold for
                            # end-of-block resolution in flush_gender_block
                            gender_orphans.append((pno, parsed, totals))
                            continue
                        gender_seen.add(band)
                        emit_gender_row(band, parsed, totals)
                        continue

                    if mode in ("state", "industry") and c0 and month_cols:
                        if "TOTAL" in c0.upper() or "PAYROLL" in c0.upper():
                            continue  # SUB TOTAL / Grand Total rows, page titles
                        if bucket is None:
                            issues.add(release, pno, mode, f"no age bucket for row {c0}")
                            continue
                        for col, ym in month_cols:
                            v = _parse_value(cells[col]) if col < len(cells) else None
                            if v is None:
                                issues.add(release, pno, f"{mode} {ym} {bucket}",
                                           f"unparseable cell for {c0!r}: {cells[col] if col < len(cells) else None!r}")
                                continue
                            name = INDUSTRY_FIXES.get(c0, c0)
                            emit("net_payroll", bucket, v,
                                 industry=name if mode == "industry" else None,
                                 state=name if mode == "state" else None, month=ym)
                        continue

                    if mode == "page1" and (ym := _abbr_month(c0)) is not None:
                        for col, b in page1_cols:
                            v = _parse_value(cells[col])
                            if v is not None:
                                page1[(ym, b)] = v
                        continue
                    # anything else (titles, notes, Total rows) is ignored
    flush_gender_block()
    return rows, page1


def parse_mospi_text_pdf(
    path: Path, release: str, issues: IssueLog, pages: tuple[int, int]
) -> list[dict]:
    """Parse the Mar-2019 MoSPI release, whose EPF tables extract as clean text
    lines: a month label, then per-band rows of 15 values
    (3 measures x male/female/transgender/not-available/total)."""
    rows: list[dict] = []
    band_re = re.compile(
        r"^(Less than 18|18-21|22-25|26-28|29-35|More than 35)\s+(.+)$"
    )
    period: str | None = None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[pages[0] : pages[1]]:
            for line in (page.extract_text() or "").splitlines():
                line = line.strip()
                if re.match(r"^2\.2\s", line):
                    return rows  # section 2.2 (ESI) ends the EPF tables
                if (ym := _full_month(line)) is not None:
                    period = ym
                    continue
                m = band_re.match(line)
                if not m or period is None:
                    continue
                band = _BAND_MAP[m.group(1).lower()]
                vals = [_parse_value(t) for t in m.group(2).split()]
                if len(vals) != 15 or None in vals:
                    issues.add(release, page.page_number, f"text {period} {band}",
                               f"expected 15 values, got: {m.group(2)!r}")
                    continue
                ok = True
                for i, measure in enumerate(MEASURES_GENDER):
                    g4, total = vals[i * 5 : i * 5 + 4], vals[i * 5 + 4]
                    if sum(g4) != total:
                        issues.add(release, page.page_number,
                                   f"text {period} {band} {measure}",
                                   f"row-sum mismatch: {g4} vs {total}")
                        ok = False
                if not ok:
                    continue
                for i, measure in enumerate(MEASURES_GENDER):
                    for g, v in zip(
                        ["male", "female", "transgender", "not_available"],
                        vals[i * 5 : i * 5 + 4],
                    ):
                        rows.append(
                            {"data_month": period, "source_release": release,
                             "measure": measure, "age_band": band, "gender": g,
                             "industry": None, "state": None, "value": v}
                        )
                    rows.append(
                        {"data_month": period, "source_release": release,
                         "measure": measure, "age_band": band, "gender": None,
                         "industry": None, "state": None, "value": vals[i * 5 + 4]}
                    )
    return rows


def _check_range(rows: list[dict], release: str, lo: str, hi: str) -> None:
    months = {r["data_month"] for r in rows}
    out = sorted(m for m in months if not lo <= m <= hi)
    if out:
        raise ValueError(f"{release}: months outside expected {lo}..{hi}: {out}")


def parse_all() -> tuple[pl.DataFrame, IssueLog, dict]:
    epfo_raw = raw_dir() / "epfo"
    issues = IssueLog()
    all_rows: list[dict] = []
    page1_mismatches = 0

    for fname, release, lo, hi in EPFO_SOURCES:
        rows, page1 = parse_epfo_pdf(epfo_raw / fname, release, issues)
        _check_range(rows, release, lo, hi)
        # cross-check: page-1 net payroll must equal section-2 column (d)
        flow_net = {
            (r["data_month"], r["age_band"]): r["value"]
            for r in rows
            if r["measure"] == "net_payroll" and r["gender"] is None
            and r["state"] is None and r["industry"] is None
        }
        for key, v in page1.items():
            if key in flow_net and flow_net[key] != v:
                issues.add(release, 1, f"page1-vs-flow {key}",
                           f"page1={v} flow={flow_net[key]}")
                page1_mismatches += 1
        all_rows.extend(rows)

    fname, release, lo, hi, pages = MOSPI_TEXT_SOURCE
    rows = parse_mospi_text_pdf(epfo_raw / fname, release, issues, pages)
    _check_range(rows, release, lo, hi)
    all_rows.extend(rows)

    fname, release, lo, hi, pages = MOSPI_TABLE_SOURCE
    rows, _ = parse_epfo_pdf(
        epfo_raw / fname, release, issues, pages=pages, national_from_gender_total=True
    )
    _check_range(rows, release, lo, hi)
    all_rows.extend(rows)

    df = pl.DataFrame(all_rows, schema={
        "data_month": pl.Utf8, "source_release": pl.Utf8, "measure": pl.Utf8,
        "age_band": pl.Utf8, "gender": pl.Utf8, "industry": pl.Utf8,
        "state": pl.Utf8, "value": pl.Int64,
    })
    df = df.with_columns(
        (pl.col("data_month") < SERIES_BREAK_BEFORE).alias("series_break_flag")
    ).sort(["data_month", "measure", "age_band", "gender", "state", "industry"])

    key = ["data_month", "measure", "age_band", "gender", "industry", "state"]
    dupes = df.group_by(key).len().filter(pl.col("len") > 1)
    if dupes.height:
        raise ValueError(f"duplicate panel keys:\n{dupes.head(10)}")

    neg = df.filter(
        (pl.col("measure") != "net_payroll") & (pl.col("value") < 0)
    )
    if neg.height:
        raise ValueError(f"negative values in gross measures:\n{neg.head(10)}")

    return df, issues, {"page1_mismatches": page1_mismatches}


def _national(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter(
        pl.col("gender").is_null() & pl.col("state").is_null()
        & pl.col("industry").is_null()
    )


def sanity_report(df: pl.DataFrame) -> dict:
    nat = _national(df)
    months = sorted(nat["data_month"].unique().to_list())
    gaps = []
    y, m = map(int, months[0].split("-"))
    for ym in months[1:]:
        m += 1
        if m == 13:
            y, m = y + 1, 1
        while f"{y}-{m:02d}" < ym:
            gaps.append(f"{y}-{m:02d}")
            m += 1
            if m == 13:
                y, m = y + 1, 1
    net = (
        nat.filter(pl.col("measure") == "net_payroll")
        .group_by("data_month").agg(pl.col("value").sum())
        .sort("data_month")
    )
    last12 = net.tail(12)
    young = (
        nat.filter(
            (pl.col("measure") == "net_payroll")
            & pl.col("age_band").is_in(["18-21", "22-25"])
        )
        .group_by("data_month").agg(pl.col("value").sum())
        .sort("data_month").tail(12)
    )
    covid = nat.filter(
        (pl.col("measure") == "net_payroll")
        & pl.col("data_month").is_in(["2020-04", "2020-05"])
        & (pl.col("value") < 0)
    )
    over35_neg = nat.filter(
        (pl.col("measure") == "net_payroll") & (pl.col("age_band") == ">35")
        & (pl.col("value") < 0)
    )
    report = {
        "months_first": months[0],
        "months_last": months[-1],
        "n_months": len(months),
        "gap_months": gaps,
        "net_last12_mean": round(last12["value"].mean()),
        "young_share_last12": round(
            young["value"].sum() / last12["value"].sum(), 3
        ),
        "covid_negative_cells": covid.height,
        "over35_negative_months": over35_neg.height,
        "months_by_dimension": {
            "national": len(months),
            "gender": df.filter(pl.col("gender").is_not_null())["data_month"].n_unique(),
            "state": df.filter(pl.col("state").is_not_null())["data_month"].n_unique(),
            "industry": df.filter(pl.col("industry").is_not_null())["data_month"].n_unique(),
        },
        "n_states": df["state"].drop_nulls().n_unique(),
        "n_industries": df["industry"].drop_nulls().n_unique(),
    }
    return report


def main() -> None:
    out_dir = processed_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    df, issues, checks = parse_all()
    epfo_payroll.validate(df, lazy=True)  # hard fail with samples (Golden Rule)

    issue_path = logs_dir() / "epfo_parse_issues.csv"
    issues.write(issue_path)

    path = out_dir / "epfo_payroll.parquet"
    df.write_parquet(path)
    report = sanity_report(df)
    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "n_rows": df.height,
        "sources": [
            {"file": f"data/raw/epfo/{f}", "source_release": r, "months": f"{lo}..{hi}"}
            for f, r, lo, hi in EPFO_SOURCES
        ]
        + [
            {"file": f"data/raw/epfo/{s[0]}", "source_release": s[1],
             "months": f"{s[2]}..{s[3]}"}
            for s in (MOSPI_TEXT_SOURCE, MOSPI_TABLE_SOURCE)
        ],
        "coverage": report,
        "known_unrecoverable_months": ["2019-02", "2019-03"]
        + [f"2019-{m}" for m in ("11", "12")]
        + [f"2020-{m:02d}" for m in range(1, 4)],
        "page1_vs_flow_mismatches": checks["page1_mismatches"],
        "n_parse_issues": len(issues.rows),
        "notes": "see data/raw/epfo/NOTES.md for series breaks and vintage caveats",
    }
    (out_dir / "epfo_payroll.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    if issues.rows:
        print(f"\n{len(issues.rows)} parse issues logged to {issue_path}")


if __name__ == "__main__":
    main()
