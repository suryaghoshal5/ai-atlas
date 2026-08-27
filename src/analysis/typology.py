"""Occupation typology: cluster the NCO 3-digit groups on exposure + workforce
composition features (PRELIMINARY per D6).

Features per group (employment-weighted within group, PLFS 2023-24):
    alpha        chat-only exposure (E1 task share)
    e2_share     tooling-dependent exposure (zeta - alpha)
    grad_share   share of workers with graduate+ education
    female_share, urban_share, young_share (18-29)
    log_median_earn  log median monthly earnings (earners only)

Method: standardize features -> k-means (seed 42, n_init 50) -> k chosen by
silhouette over k = 3..7. Groups are unweighted points (each occupation counts
once); employment enters the interpretation, not the fit.

Outputs:
    data/processed/occupation_typology_PRELIMINARY.parquet
    outputs/tables/typology_profiles_PRELIMINARY.csv
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import polars as pl
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from atlas_common import outputs_dir, processed_dir, run_seed


def build_features() -> pl.DataFrame:
    df = (pl.read_parquet(processed_dir() / "plfs_exposure_PRELIMINARY.parquet")
          .filter(pl.col("beta").is_not_null()))
    idx = pl.read_parquet(processed_dir() / "group3_index_PRELIMINARY.parquet")
    earn = df.filter(pl.col("monthly_earnings") > 0)
    feats = (
        df.group_by("group3")
        .agg(
            (pl.col("weight").sum() / 1e6).alias("workers_m"),
            ((pl.col("edu_code").is_in([10, 11, 12, 13])).cast(pl.Float64) * pl.col("weight"))
            .sum().alias("_grad_w"),
            ((pl.col("sex_code") == 2).cast(pl.Float64) * pl.col("weight")).sum().alias("_fem_w"),
            ((pl.col("sector_code") == 2).cast(pl.Float64) * pl.col("weight")).sum().alias("_urb_w"),
            (((pl.col("age") >= 18) & (pl.col("age") <= 29)).cast(pl.Float64) * pl.col("weight"))
            .sum().alias("_yng_w"),
            pl.col("weight").sum().alias("_w"),
        )
        .with_columns(
            (pl.col("_grad_w") / pl.col("_w")).alias("grad_share"),
            (pl.col("_fem_w") / pl.col("_w")).alias("female_share"),
            (pl.col("_urb_w") / pl.col("_w")).alias("urban_share"),
            (pl.col("_yng_w") / pl.col("_w")).alias("young_share"),
        )
        .join(earn.group_by("group3").agg(pl.col("monthly_earnings").median().alias("med_earn")),
              on="group3", how="left")
        .join(idx.filter(pl.col("n_tasks") >= 5)
              .select("group3", "alpha", (pl.col("zeta") - pl.col("alpha")).alias("e2_share")),
              on="group3", how="inner")
        .with_columns(pl.col("med_earn").fill_null(pl.col("med_earn").median()).log().alias("log_med_earn"))
        .select("group3", "workers_m", "alpha", "e2_share", "grad_share",
                "female_share", "urban_share", "young_share", "log_med_earn")
        .sort("group3")
    )
    return feats


FEATURES = ["alpha", "e2_share", "grad_share", "female_share",
            "urban_share", "young_share", "log_med_earn"]


def main() -> None:
    feats = build_features()
    X = StandardScaler().fit_transform(feats.select(FEATURES).to_numpy())

    sil = {}
    fits = {}
    for k in range(3, 8):
        km = KMeans(n_clusters=k, n_init=50, random_state=run_seed())
        lab = km.fit_predict(X)
        sil[k] = float(silhouette_score(X, lab))
        fits[k] = lab
    best_k = max(sil, key=sil.get)
    labels = fits[best_k]
    out = feats.with_columns(pl.Series("cluster", labels))

    profile = (
        out.group_by("cluster")
        .agg(
            pl.len().alias("n_groups"),
            pl.col("workers_m").sum().alias("workers_m"),
            *[((pl.col(f) * pl.col("workers_m")).sum() / pl.col("workers_m").sum()).round(3).alias(f)
              for f in FEATURES],
        )
        .sort("cluster")
    )
    tables = outputs_dir() / "tables"
    out.write_parquet(processed_dir() / "occupation_typology_PRELIMINARY.parquet")
    profile.write_csv(tables / "typology_profiles_PRELIMINARY.csv")

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRELIMINARY per D6",
        "method": f"k-means, standardized features, n_init=50, seed={run_seed()}",
        "silhouette_by_k": {str(k): round(v, 3) for k, v in sil.items()},
        "chosen_k": best_k,
        "features": FEATURES,
    }
    (processed_dir() / "occupation_typology_PRELIMINARY.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta["silhouette_by_k"], indent=1), "-> k =", best_k)
    with pl.Config(tbl_cols=12, tbl_width_chars=140):
        print(profile)
    # biggest groups per cluster for naming
    for c in sorted(set(labels)):
        top = out.filter(pl.col("cluster") == c).sort("workers_m", descending=True).head(5)
        print(f"cluster {c}:", ", ".join(f"{r['group3']}({r['workers_m']:.1f}M)"
                                          for r in top.iter_rows(named=True)))


if __name__ == "__main__":
    main()
