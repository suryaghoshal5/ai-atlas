"""Master tables: one file per grain, joinable but never merged.

Three grains, because the sources have three. Tasks are the unit the rubric
scores (18.6k rows), occupation groups are the unit the index and PLFS meet
(122 rows), and NAS activity heads are the unit GVA and EPFO live at (8 rows).
A single flat file across all three cannot be built honestly: occupations span
sectors, so a task row carrying "its" workers, GVA and payroll would be an
allocation invented here, not a join — exactly the silent approximation Golden
Rule 1 forbids. The keys are published instead:

    task_master.group3  -> occupation_master.group3
    occupation_master   -> sector_master: NO key. Occupations span sectors; the
                           only honest link is the worker-level PLFS file,
                           where each worker carries both an occupation and an
                           industry. Ask that file, not these two.

Outputs (all PRELIMINARY per D6 — LLM-only scores, no kappa gate):
    outputs/tables/task_master_PRELIMINARY.csv
    outputs/tables/occupation_master_PRELIMINARY.csv
    outputs/tables/sector_master_PRELIMINARY.csv
    outputs/tables/masters_PRELIMINARY.meta.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import polars as pl
import yaml

from atlas_common import REPO_ROOT, outputs_dir, processed_dir
from atlas_common.nco_labels import NAMES
from atlas_common.sectors import GVA_TOTAL, NAS
from atlas_common.stats import weighted_median_by

SCORES = outputs_dir() / "full_batch_scoring" / "task_scores_full_PRELIMINARY.parquet"
GRAD_CODES = [10, 11, 12, 13]
YOUNG_AGE = (18, 29)
HIGH_EXPOSURE_BETA = 0.5
ENTRY_AGE_BANDS = ["<18", "18-21", "22-25"]
EPFO_WINDOW_MONTHS = 12


# ---------------------------------------------------------------- shared bits

def wshare(cond: pl.Expr) -> pl.Expr:
    return (cond.cast(pl.Float64) * pl.col("weight")).sum() / pl.col("weight").sum()


def plfs_aggregates(df: pl.DataFrame, key: str) -> pl.DataFrame:
    """The PLFS block every master shares: headcount, exposure, earnings and
    composition, all survey-weighted (weight = mult/no_qtr).

    Earnings are salaried + self-employed monthly earnings; casual daily wages
    are not folded in yet (see merge.plfs), so levels understate wherever
    casual work is common. Medians and the formality share are computed on
    their own defined subsets (earners; records with a non-null benefit code),
    never by treating a missing value as a zero.
    """
    agg = (
        df.group_by(key)
        .agg(
            pl.len().alias("n_records"),
            (pl.col("weight").sum() / 1e6).alias("workers_m"),
            ((pl.col("beta") * pl.col("weight")).sum() / pl.col("weight").sum()).alias("mean_beta"),
            ((pl.col("alpha") * pl.col("weight")).sum() / pl.col("weight").sum()).alias("mean_alpha"),
            (((pl.col("zeta") - pl.col("alpha")) * pl.col("weight")).sum()
             / pl.col("weight").sum()).alias("mean_e2_share"),
            wshare(pl.col("beta") >= HIGH_EXPOSURE_BETA).alias("high_exposure_share"),
            wshare(pl.col("sex_code") == 2).alias("female_share"),
            wshare(pl.col("sector_code") == 2).alias("urban_share"),
            wshare(pl.col("edu_code").is_in(GRAD_CODES)).alias("grad_share"),
            wshare((pl.col("age") >= YOUNG_AGE[0]) & (pl.col("age") <= YOUNG_AGE[1]))
            .alias("young_share"),
            ((pl.col("monthly_earnings") * pl.col("weight")).sum() / 1e6)
            .alias("monthly_wage_bill_inr_m"),
            (pl.col("weight").filter(pl.col("monthly_earnings") > 0).sum())
            .alias("_earner_weight"),
            # formality is a social-security PROXY and is undefined for many
            # records; share is over records where it IS defined
            (pl.col("weight").filter(pl.col("formal_proxy")).sum()
             / pl.col("weight").filter(pl.col("formal_proxy").is_not_null()).sum())
            .alias("formal_proxy_share"),
        )
    )
    earners = df.filter(pl.col("monthly_earnings") > 0)
    med = weighted_median_by(earners, key, "monthly_earnings", "weight",
                             "median_monthly_earnings_inr")
    mean = (earners.group_by(key)
            .agg(((pl.col("monthly_earnings") * pl.col("weight")).sum()
                  / pl.col("weight").sum()).alias("mean_monthly_earnings_inr")))
    total_weight = float(df["weight"].sum())
    total_wage_bill = float((df["monthly_earnings"] * df["weight"]).sum())
    return (
        agg.join(med, on=key, how="left").join(mean, on=key, how="left")
        .with_columns(
            (pl.col("workers_m") * 1e6 / total_weight).alias("employment_share"),
            (pl.col("monthly_wage_bill_inr_m") * 1e6 / total_wage_bill).alias("wage_bill_share"),
            (pl.col("_earner_weight") / (pl.col("workers_m") * 1e6)).alias("earner_share"),
        )
        .drop("_earner_weight")
    )


def load_workers() -> pl.DataFrame:
    return (pl.read_parquet(processed_dir() / "plfs_exposure_PRELIMINARY.parquet")
            .filter(pl.col("beta").is_not_null()))


def hierarchy(code_col: str = "group3") -> list[pl.Expr]:
    """NCO-2015 is a nested digit hierarchy: division (1) > sub-division (2) >
    group (3) > family (4) > occupation (8). Only the 8-digit titles are parsed
    (Vol II); titles for the levels above need Vol I, which has no parser yet —
    so the levels above ship as codes, plus our editorial 3-digit label."""
    return [
        pl.col(code_col).str.slice(0, 1).alias("division1"),
        pl.col(code_col).str.slice(0, 2).alias("sub_division2"),
    ]


def editorial_label(code_col: str = "group3") -> pl.Expr:
    """Attach labels by KEY, never by position — a join may reorder rows, and a
    positionally-attached label would then name the wrong occupation."""
    return (pl.col(code_col).replace_strict(NAMES, default=None, return_dtype=pl.Utf8)
            .alias("group3_label"))


# --------------------------------------------------------------- task master

def build_task_master() -> pl.DataFrame:
    tasks = pl.read_parquet(processed_dir() / "task_statements_full.parquet")
    scores = pl.read_parquet(SCORES)
    grp = (pl.read_parquet(processed_dir() / "group3_index_PRELIMINARY.parquet")
           .select("group3",
                   pl.col("n_tasks").alias("group3_n_tasks"),
                   pl.col("alpha").alias("group3_alpha"),
                   pl.col("beta").alias("group3_beta"),
                   pl.col("zeta").alias("group3_zeta")))
    occ = (pl.read_parquet(processed_dir() / "occupation_index_PRELIMINARY.parquet")
           .select("nco_code",
                   pl.col("n_tasks").alias("occupation_n_tasks"),
                   pl.col("beta").alias("occupation_beta")))

    out = (
        tasks.join(scores.select("task_id", "score", "rubric_version", "model",
                                 "n_samples", "preliminary"),
                   on="task_id", how="left")
        .join(occ, on="nco_code", how="left")
        .join(grp, on="group3", how="left")
        .with_columns(
            *hierarchy(),
            pl.col("family").alias("family4"),
            pl.col("score").is_not_null().alias("scored"),
            pl.col("score").is_in(["E1", "E2"]).alias("exposed"),
            editorial_label(),
        )
        .select(
            "task_id", "nco_code", "division1", "sub_division2", "group3", "family4",
            "occupation_title", "group3_label", "task_text",
            "scored", "score", "exposed",
            "occupation_n_tasks", "occupation_beta",
            "group3_n_tasks", "group3_alpha", "group3_beta", "group3_zeta",
            "rubric_version", "model", "n_samples", "preliminary",
        )
        .sort("task_id")
    )
    return out


# --------------------------------------------------------- occupation master

def build_occupation_master(workers: pl.DataFrame) -> pl.DataFrame:
    idx = pl.read_parquet(processed_dir() / "group3_index_PRELIMINARY.parquet")
    typ_path = processed_dir() / "occupation_typology_PRELIMINARY.parquet"
    agg = plfs_aggregates(workers, "group3")

    out = (
        idx.select("group3", "n_tasks", "alpha", "beta", "zeta",
                   (pl.col("zeta") - pl.col("alpha")).alias("e2_share"),
                   "rubric_version", "preliminary")
        .join(agg, on="group3", how="left")
        .with_columns(*hierarchy(), editorial_label(),
                      (pl.col("beta") >= HIGH_EXPOSURE_BETA).alias("high_exposure"))
    )
    if typ_path.exists():
        typ = pl.read_parquet(typ_path)
        if "name" in typ.columns:
            out = out.join(typ.select("group3", "cluster",
                                      pl.col("name").alias("cluster_name")),
                           on="group3", how="left")
    if "cluster_name" not in out.columns:
        out = out.with_columns(pl.lit(None, dtype=pl.Int32).alias("cluster"),
                               pl.lit(None, dtype=pl.Utf8).alias("cluster_name"))
    front = ["group3", "group3_label", "division1", "sub_division2", "n_tasks",
             "alpha", "beta", "zeta", "e2_share", "high_exposure",
             "cluster", "cluster_name"]
    return out.select(front + [c for c in out.columns if c not in front]).sort("group3")


# ------------------------------------------------------------- sector master

def with_nas_head(df: pl.DataFrame) -> pl.DataFrame:
    nic2 = pl.col("nic5").cast(pl.Utf8).str.zfill(5).str.slice(0, 2).cast(pl.Int32, strict=False)
    head = pl.lit(None, dtype=pl.Utf8)
    for label, _, divs in NAS[::-1]:
        head = pl.when(nic2.is_in(divs)).then(pl.lit(label)).otherwise(head)
    return df.with_columns(nic2.alias("nic2"), head.alias("nas_head"))


def epfo_by_nas_head() -> tuple[pl.DataFrame, dict]:
    """EPFO net payroll folded onto NAS heads by CONTAINMENT.

    EPFO industry heads are establishment classes, not NIC divisions, and the
    hand-authored crosswalk's division sets overlap — they characterise heads,
    they do not partition the economy. So a head is credited to a NAS head only
    when every division it maps to sits inside that NAS head; a head straddling
    two NAS heads (engineering contractors: 33, 42, 71) is left UNALLOCATED and
    reported, never split. Splitting would require a payroll-share assumption
    this project does not have.
    """
    epfo_path = processed_dir() / "epfo_payroll.parquet"
    cw_path = REPO_ROOT / "config" / "epfo_nic_crosswalk.yaml"
    if not epfo_path.exists():
        return pl.DataFrame(), {"status": "epfo_payroll.parquet absent — EPFO columns omitted"}

    cw = yaml.safe_load(cw_path.read_text())
    div_to_head = {label: set(divs) for label, _, divs in NAS}
    assign, unallocated = {}, []
    for head, spec in cw.items():
        divs = {int(d) for d in (spec.get("nic2") or [])}
        if not divs:
            unallocated.append(head)
            continue
        owners = [nas for nas, nas_divs in div_to_head.items() if divs <= nas_divs]
        if len(owners) == 1:
            assign[head] = owners[0]
        else:
            unallocated.append(head)

    epfo = pl.read_parquet(epfo_path).filter(
        (pl.col("measure") == "net_payroll") & pl.col("industry").is_not_null())
    months = sorted(epfo["data_month"].unique().to_list())
    window = months[-EPFO_WINDOW_MONTHS:]
    recent = epfo.filter(pl.col("data_month").is_in(window))

    mapped = recent.with_columns(
        pl.col("industry").replace_strict(assign, default=None).alias("nas_head"))
    per_head = (
        mapped.filter(pl.col("nas_head").is_not_null())
        .group_by("nas_head")
        .agg(pl.col("value").sum().alias("epfo_net_payroll_window"),
             pl.col("value").filter(pl.col("age_band").is_in(ENTRY_AGE_BANDS)).sum()
             .alias("epfo_net_payroll_window_age_le25"),
             pl.col("industry").unique().sort().str.join("; ").alias("epfo_heads_mapped"))
    )
    total_abs = float(recent["value"].abs().sum()) or 1.0
    unmapped_abs = float(mapped.filter(pl.col("nas_head").is_null())["value"].abs().sum())
    meta = {
        "window": f"{window[0]}..{window[-1]}",
        "measure": "net_payroll (net of exits; negatives are legitimate)",
        "rule": "EPFO head credited to a NAS head only when its NIC divisions are "
                "wholly contained in that head; straddling heads left unallocated",
        "unallocated_heads": sorted(unallocated),
        "unallocated_share_of_abs_volume": round(unmapped_abs / total_abs, 4),
    }
    return per_head, meta


def build_sector_master(workers: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    w = with_nas_head(workers)
    matched = w.filter(pl.col("nas_head").is_not_null())
    agg = plfs_aggregates(matched, "nas_head")

    base = pl.DataFrame([
        {"nas_head": label,
         "nic2_divisions": ",".join(str(d) for d in divs),
         "gva_crore_fy2023_24": float(gva),
         "gva_share": gva / GVA_TOTAL}
        for label, gva, divs in NAS
    ])
    out = base.join(agg, on="nas_head", how="left")

    epfo, epfo_meta = epfo_by_nas_head()
    if epfo.height:
        out = out.join(epfo, on="nas_head", how="left")
    else:
        out = out.with_columns(
            pl.lit(None, dtype=pl.Int64).alias("epfo_net_payroll_window"),
            pl.lit(None, dtype=pl.Int64).alias("epfo_net_payroll_window_age_le25"),
            pl.lit(None, dtype=pl.Utf8).alias("epfo_heads_mapped"))

    unmatched_weight = float(w.filter(pl.col("nas_head").is_null())["weight"].sum())
    meta = {
        "epfo": epfo_meta,
        "plfs_employment_unmatched_to_any_nas_head":
            round(unmatched_weight / float(w["weight"].sum()), 4),
        "note": "PLFS shares in this file are of MATCHED employment (workers with a "
                "usable NIC division), not of national employment",
    }
    return out.with_columns(pl.lit(True).alias("preliminary")), meta


# ---------------------------------------------------------------------- main

def main() -> None:
    tables = outputs_dir() / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    workers = load_workers()

    task = build_task_master()
    occupation = build_occupation_master(workers)
    sector, sector_meta = build_sector_master(workers)

    task.write_csv(tables / "task_master_PRELIMINARY.csv")
    occupation.write_csv(tables / "occupation_master_PRELIMINARY.csv")
    sector.write_csv(tables / "sector_master_PRELIMINARY.csv")

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRELIMINARY per D6 — LLM-only scores, kappa gate deferred; "
                  "not for the abstract or paper",
        "task_master": {"rows": task.height,
                        "scored": int(task["scored"].sum()),
                        "unscored": int((~task["scored"]).sum()),
                        "occupations": task["nco_code"].n_unique(),
                        "groups3": task["group3"].n_unique()},
        "occupation_master": {"rows": occupation.height,
                              "with_plfs_workers": int(occupation["workers_m"].is_not_null().sum()),
                              "workers_m_total": round(float(occupation["workers_m"].sum()), 2)},
        "sector_master": {"rows": sector.height, **sector_meta},
        "earnings_concept": "salaried + self-employed monthly earnings, survey-weighted; "
                            "casual daily wages excluded (merge.plfs)",
        "keys": {"task_master.group3": "occupation_master.group3",
                 "occupation_master -> sector_master": "no key; occupations span "
                 "sectors — join at the worker level instead"},
    }
    (tables / "masters_PRELIMINARY.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
