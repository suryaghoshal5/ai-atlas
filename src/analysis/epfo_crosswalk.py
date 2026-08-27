"""EPFO industry-head exposure assignment + the §5 granularity check.

Assignment: head exposure = employment-weighted mean occupation exposure (beta)
of PLFS 2023-24 workers in the head's NIC-2008 divisions
(config/epfo_nic_crosswalk.yaml). This is the design's pre-registered
coarseness check: if exposure barely varies across usable heads, the canaries
event study demotes to a descriptive exhibit (ANALYSIS_PLAN §5 decision rule).

Statistics reported for the decision (thresholds are Surya's call, per gate):
  - head-level beta: range, IQR across usable heads
  - payroll-weighted between-head spread (weights = EPFO |net| volume)
  - variance decomposition: between-head share of worker-level exposure
    variance among mapped workers (eta-squared)

Outputs (PRELIMINARY per D6):
  outputs/tables/epfo_head_exposure_PRELIMINARY.csv
  outputs/tables/epfo_granularity_check_PRELIMINARY.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import polars as pl
import yaml

from atlas_common import REPO_ROOT, outputs_dir, processed_dir


def main() -> None:
    cw = yaml.safe_load((REPO_ROOT / "config" / "epfo_nic_crosswalk.yaml").read_text())
    workers = (
        pl.read_parquet(processed_dir() / "plfs_exposure_PRELIMINARY.parquet")
        .filter(pl.col("beta").is_not_null() & pl.col("nic5").is_not_null())
        .with_columns(pl.col("nic5").cast(pl.Utf8).str.zfill(5).str.slice(0, 2).alias("nic2"))
    )
    epfo = pl.read_parquet(processed_dir() / "epfo_payroll.parquet")
    vol = (
        epfo.filter(pl.col("industry").is_not_null())
        .group_by("industry")
        .agg(pl.col("value").abs().sum().alias("epfo_abs_volume"),
             pl.col("value").sum().alias("epfo_net_total"))
    )

    rows = []
    for head, spec in cw.items():
        nic2 = spec.get("nic2") or []
        if not nic2:
            continue
        s = workers.filter(pl.col("nic2").is_in(nic2))
        w = float(s["weight"].sum())
        if w == 0:
            continue
        mean_b = float((s["beta"] * s["weight"]).sum() / w)
        var_within = float((((s["beta"] - mean_b) ** 2) * s["weight"]).sum() / w)
        rows.append({
            "industry": head,
            "nic2": "+".join(nic2),
            "plfs_workers_m": round(w / 1e6, 2),
            "mean_beta": round(mean_b, 3),
            "sd_within": round(var_within ** 0.5, 3),
            "share_hi": round(float(s.filter(pl.col("beta") >= 0.5)["weight"].sum() / w), 3),
            "share_white_collar": round(float(
                s.filter(pl.col("group3").str.slice(0, 1).is_in(["1", "2", "3", "4"]))["weight"].sum() / w), 3),
        })
    heads = pl.DataFrame(rows).join(vol, on="industry", how="left").sort("mean_beta", descending=True)

    tables = outputs_dir() / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    heads.write_csv(tables / "epfo_head_exposure_PRELIMINARY.csv")

    # granularity statistics
    betas = heads["mean_beta"].to_list()
    v = heads["epfo_abs_volume"].fill_null(0).to_list()
    vw_mean = sum(b * x for b, x in zip(betas, v)) / sum(v)
    vw_sd = (sum(x * (b - vw_mean) ** 2 for b, x in zip(betas, v)) / sum(v)) ** 0.5

    # eta^2 among mapped workers: assign each worker its head's mean (first
    # matching head in file order) and decompose exposure variance
    assign = []
    for head, spec in cw.items():
        for d in spec.get("nic2") or []:
            assign.append({"nic2": d, "head": head})
    amap = pl.DataFrame(assign).unique(subset=["nic2"], keep="first")
    mw = workers.join(amap, on="nic2", how="inner")
    gm = float((mw["beta"] * mw["weight"]).sum() / mw["weight"].sum())
    head_means = mw.group_by("head").agg(
        ((pl.col("beta") * pl.col("weight")).sum() / pl.col("weight").sum()).alias("hb"),
        pl.col("weight").sum().alias("hw"))
    between = float(((head_means["hb"] - gm) ** 2 * head_means["hw"]).sum() / head_means["hw"].sum())
    total = float((((mw["beta"] - gm) ** 2) * mw["weight"]).sum() / mw["weight"].sum())

    stats = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRELIMINARY per D6; crosswalk v0.1 is hand-authored judgment",
        "n_usable_heads": heads.height,
        "beta_range": [round(min(betas), 3), round(max(betas), 3)],
        "beta_iqr": [round(sorted(betas)[len(betas)//4], 3), round(sorted(betas)[3*len(betas)//4], 3)],
        "payroll_weighted_mean_beta": round(vw_mean, 3),
        "payroll_weighted_sd_beta": round(vw_sd, 3),
        "between_head_variance_share_eta2": round(between / total, 3),
        "mapped_plfs_employment_share": round(float(mw["weight"].sum() / workers["weight"].sum()), 3),
        "excluded_heads": ["OTHERS (unmappable; large volume — limitation)"],
        "decision_rule": "ANALYSIS_PLAN §5: demote to descriptive if cross-head exposure variation is insufficient — threshold is Surya's gated call",
    }
    (tables / "epfo_granularity_check_PRELIMINARY.json").write_text(json.dumps(stats, indent=2))
    with pl.Config(fmt_str_lengths=50, tbl_rows=20):
        print(heads.select("industry", "mean_beta", "sd_within", "share_hi",
                           "share_white_collar", "plfs_workers_m", "epfo_net_total"))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
