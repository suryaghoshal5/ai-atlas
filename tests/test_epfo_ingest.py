"""EPFO payroll ingest: schema contract + hard-coded spot checks against
values verified by eye in the raw PDFs (page citations in each test).

Run `PYTHONPATH=src uv run python -m ingest.epfo` first; tests skip if the
processed parquet is absent."""

import polars as pl
import pytest

from atlas_common import processed_dir, schemas

PARQUET = processed_dir() / "epfo_payroll.parquet"

KNOWN_GAPS = {"2019-02", "2019-03", "2019-11", "2019-12", "2020-01", "2020-02", "2020-03"}


@pytest.fixture(scope="module")
def df() -> pl.DataFrame:
    if not PARQUET.exists():
        pytest.skip("run `python -m ingest.epfo` to build data/processed/epfo_payroll.parquet")
    return pl.read_parquet(PARQUET)


def _one(df, **kw):
    f = df
    for k, v in kw.items():
        f = f.filter(pl.col(k).is_null() if v is None else pl.col(k) == v)
    assert f.height == 1, f"expected exactly one row for {kw}, got {f.height}"
    return f["value"][0]


def test_schema_validates(df):
    schemas.epfo_payroll.validate(df, lazy=True)


def test_spot_check_national_flow(df):
    # epfo_September-2025.pdf p.7, "April 2025" block, 18-21 row: (a) 297523,
    # (b) 171826, (c) 167982, (d) 293679 — verified by eye.
    base = dict(data_month="2025-04", age_band="18-21", gender=None, state=None, industry=None)
    assert _one(df, measure="new_subscribers", **base) == 297523
    assert _one(df, measure="ceased", **base) == 171826
    assert _one(df, measure="rejoined", **base) == 167982
    assert _one(df, measure="net_payroll", **base) == 293679


def test_spot_check_covid_vintage(df):
    # epfo_May-2021-1.pdf p.1 monthly table: Apr-2020, <18 = 861 and
    # 18-21 = -24931 (COVID negative) — verified by eye.
    base = dict(data_month="2020-04", measure="net_payroll", gender=None, state=None, industry=None)
    assert _one(df, age_band="<18", **base) == 861
    assert _one(df, age_band="18-21", **base) == -24931


def test_spot_check_mospi_gender(df):
    # MoSPI 25-Mar-2019 release ("...January_2019_250319_Release_.pdf") p.1,
    # September 2017 block, 18-21: male new 2,38,197; total new 2,82,914.
    assert _one(df, data_month="2017-09", measure="new_subscribers",
                age_band="18-21", gender="male") == 238197
    assert _one(df, data_month="2017-09", measure="new_subscribers",
                age_band="18-21", gender=None, state=None, industry=None) == 282914


def test_spot_check_state_and_industry(df):
    # epfo_September-2025.pdf p.14 (state, "Less than 18"): TAMIL NADU Jul-25 = 1772.
    assert _one(df, data_month="2025-07", state="TAMIL NADU", age_band="<18") == 1772
    # epfo_September-2025.pdf p.20 (industry, "18-21"): EXPERT SERVICES Apr-25 = 144499.
    assert _one(df, data_month="2025-04", industry="EXPERT SERVICES", age_band="18-21") == 144499


def test_month_coverage_and_gaps(df):
    months = set(df["data_month"].unique().to_list())
    assert min(months) == "2017-09" and max(months) >= "2025-07"
    span = []
    y, m = 2017, 9
    while (ym := f"{y}-{m:02d}") <= max(months):
        span.append(ym)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    assert set(span) - months == KNOWN_GAPS


def test_gender_sums_match_national(df):
    nat = df.filter(
        pl.col("gender").is_null() & pl.col("state").is_null()
        & pl.col("industry").is_null() & (pl.col("measure") != "net_payroll")
    )
    gsum = (
        df.filter(pl.col("gender").is_not_null())
        .group_by(["data_month", "measure", "age_band"])
        .agg(pl.col("value").sum().alias("gsum"))
    )
    j = gsum.join(nat, on=["data_month", "measure", "age_band"], how="inner")
    assert j.height == nat.height
    assert j.filter(pl.col("gsum") != pl.col("value")).height == 0


def test_flow_identity(df):
    nat = df.filter(
        pl.col("gender").is_null() & pl.col("state").is_null() & pl.col("industry").is_null()
    )
    wide = nat.pivot(on="measure", index=["data_month", "age_band"], values="value")
    epfo_era = wide.filter(pl.col("net_payroll").is_not_null())
    bad = epfo_era.filter(
        pl.col("new_subscribers") - pl.col("ceased") + pl.col("rejoined")
        != pl.col("net_payroll")
    )
    assert bad.height == 0


def test_series_break_flag(df):
    assert df.filter(pl.col("series_break_flag"))["data_month"].max() < "2020-04"
    assert df.filter(~pl.col("series_break_flag"))["data_month"].min() == "2020-04"
    # pre-break segment has no net_payroll (MoSPI regime)
    assert df.filter(
        pl.col("series_break_flag") & (pl.col("measure") == "net_payroll")
    ).height == 0
