"""Merge the exposure index onto PLFS 2023-24 worker records (ANALYSIS_PLAN §3).

Column mapping verified against docs/Data_LayoutPLFS_2023-24.xlsx (perv1 sheet):
    b1q3       sector (1 rural, 2 urban)
    b4q5       sex (1 male, 2 female, 3 transgender)
    b4q6       age
    b4q8       general education level (NSS codes)
    b5pt1q3    usual principal status code (11-51 employed)
    b5pt1q5    NIC-2008 industry (5-digit)
    b5pt1q6    NCO-2015 occupation (3-digit)
    b5pt1q13   social security benefits (1-8 some, 9 none) -> formality PROXY
    b6q9/b6q10 monthly earnings: regular salaried / self-employed
               (casual daily wages in block 6 activities NOT yet folded in —
               wage-bill exhibits exclude casual earnings for now, stated)
    mult/no_qtr survey multiplier; weight = mult / no_qtr

STOP rule: if <90% of employed weight matches an index group3, halt with the
unmatched list (config merge.min_plfs_weight_coverage).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import polars as pl

from atlas_common import load_config, processed_dir, raw_dir

EMPLOYED_PAS = [11, 12, 21, 31, 41, 51]

COLS = {
    "b1q3_perv1": "sector_code",
    "state_perv1": "state",
    "b4q5_perv1": "sex_code",
    "b4q6_perv1": "age",
    "b4q8_perv1": "edu_code",
    "b5pt1q3_perv1": "status_code",
    "b5pt1q5_perv1": "nic5",
    "b5pt1q6_perv1": "nco3_raw",
    "b5pt1q13_perv1": "ss_benefit_code",
    "b6q9_perv1": "earnings_regular",
    "b6q10_perv1": "earnings_self",
    "mult_perv1": "mult",
    "no_qtr_perv1": "no_qtr",
}


def load_workers(year_dir: str = "plfs_2023-24_jul-jun") -> pl.DataFrame:
    path = raw_dir() / "plfs" / year_dir / "csv" / "perv1.csv"
    df = (
        pl.scan_csv(path, infer_schema_length=10000)
        .select(list(COLS.keys()))
        .rename(COLS)
        .filter(pl.col("status_code").is_in(EMPLOYED_PAS))
        .with_columns(
            pl.col("nco3_raw").cast(pl.Utf8).str.zfill(3).alias("group3"),
            (pl.col("mult") / pl.col("no_qtr")).alias("weight"),
            (pl.col("earnings_regular").fill_null(0) + pl.col("earnings_self").fill_null(0))
            .alias("monthly_earnings"),
            # instruction manual p.88: 1-7 = eligible for some benefit, 8 = not
            # eligible for any, 9 = not known (asked of regular/salaried & casual)
            pl.when(pl.col("ss_benefit_code").is_in([1, 2, 3, 4, 5, 6, 7]))
            .then(True).when(pl.col("ss_benefit_code") == 8).then(False)
            .otherwise(None).alias("formal_proxy"),
        )
        .collect()
    )
    # hard sanity asserts — never coerce silently (Golden Rule 6 spirit)
    assert df["sex_code"].is_in([1, 2, 3]).all(), "unexpected sex codes"
    assert df["age"].is_between(0, 120).all(), "ages out of range"
    assert df["sector_code"].is_in([1, 2]).all(), "unexpected sector codes"
    assert (df["weight"] > 0).all(), "non-positive weights"
    return df


def main() -> None:
    cfg = load_config()
    idx = pl.read_parquet(processed_dir() / "group3_index_PRELIMINARY.parquet")
    workers = load_workers()

    merged = workers.join(idx.select("group3", "n_tasks", "alpha", "beta", "zeta"),
                          on="group3", how="left")
    w_total = merged["weight"].sum()
    w_matched = merged.filter(pl.col("beta").is_not_null())["weight"].sum()
    coverage = w_matched / w_total
    unmatched = (
        merged.filter(pl.col("beta").is_null())
        .group_by("group3").agg(pl.col("weight").sum())
        .with_columns((pl.col("weight") / w_total).alias("emp_share"))
        .sort("emp_share", descending=True)
    )
    if coverage < cfg["merge"]["min_plfs_weight_coverage"]:
        print(unmatched)
        raise SystemExit(f"STOP: only {coverage:.1%} of employment weight matched "
                         f"(< {cfg['merge']['min_plfs_weight_coverage']:.0%}).")

    merged = merged.with_columns(pl.lit(True).alias("preliminary"),
                                 pl.lit("2023-24").alias("survey_year"))
    out = processed_dir() / "plfs_exposure_PRELIMINARY.parquet"
    merged.write_parquet(out)

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRELIMINARY per D6 — not for paper/abstract",
        "n_workers": merged.height,
        "employment_weight_coverage": round(float(coverage), 4),
        "unmatched_groups": {r["group3"]: round(r["emp_share"], 5)
                             for r in unmatched.iter_rows(named=True)},
        "notes": [
            "weight = mult/no_qtr; principal usual status employed only",
            "formality is a social-security-benefits PROXY (b5pt1q13), not the full PLFS formality definition",
            "monthly_earnings excludes casual daily wages (block 6 activity-level) for now",
        ],
    }
    (processed_dir() / "plfs_exposure_PRELIMINARY.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
