"""Occupation typology: cluster the NCO 3-digit groups on exposure + workforce
composition features (PRELIMINARY per D6).

Features per group (PLFS 2023-24, survey-weighted throughout):
    alpha        chat-only exposure (E1 task share)
    e2_share     tooling-dependent exposure (zeta - alpha)
    grad_share   share of workers with graduate+ education
    female_share, urban_share, young_share (18-29)
    log_median_earn  log of the survey-weighted median monthly earnings
                     (earners only; salaried + self-employed, casual daily
                     wages not yet folded in - see merge.plfs)

Method: standardize features -> k-means (seed 42, n_init 50) -> k chosen by
silhouette over k = 3..7. Groups are unweighted points (each occupation counts
once); employment enters the interpretation, not the fit.

Cluster profiles are computed from the pooled PLFS unit records of each
cluster, survey-weighted: the earnings row is a true worker-level weighted
median, NOT an average of group-level medians.

Cluster ids from k-means are arbitrary and move whenever the features or the
data move, so cluster NAMES are resolved from the profile (see name_clusters)
and every downstream exhibit keys off the name.

Outputs:
    data/processed/occupation_typology_PRELIMINARY.parquet
    outputs/tables/typology_profiles_PRELIMINARY.csv
    paper/whitepaper/tables/typology_clusters_PRELIMINARY.md
      (also spliced into the generated block in white paper section 8b)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import polars as pl
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from atlas_common import outputs_dir, paper_dir, processed_dir, run_seed
from atlas_common.nco_labels import label
from atlas_common.stats import weighted_median

HIGH_EXPOSURE_BETA = 0.5

BEGIN_MARK = "<!-- BEGIN generated: analysis.typology cluster profiles - do not edit by hand -->"
END_MARK = "<!-- END generated: analysis.typology cluster profiles -->"


def load_workers() -> pl.DataFrame:
    return (pl.read_parquet(processed_dir() / "plfs_exposure_PRELIMINARY.parquet")
            .filter(pl.col("beta").is_not_null()))


def weighted_median_by(df: pl.DataFrame, key: str, value: str, weight: str,
                       alias: str) -> pl.DataFrame:
    """Survey-weighted median of `value` within each `key` (polars has no
    weighted quantile; the groups are few, so an explicit partition is fine)."""
    rows = [{key: part[key][0],
             alias: weighted_median(part[value].to_numpy(), part[weight].to_numpy())}
            for part in df.partition_by(key, maintain_order=True)]
    return pl.DataFrame(rows, schema={key: df.schema[key], alias: pl.Float64})


def build_features(df: pl.DataFrame) -> pl.DataFrame:
    idx = pl.read_parquet(processed_dir() / "group3_index_PRELIMINARY.parquet")
    earners = df.filter(pl.col("monthly_earnings") > 0)
    med = weighted_median_by(earners, "group3", "monthly_earnings", "weight", "med_earn")
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
        .join(med, on="group3", how="left")
        .join(idx.filter(pl.col("n_tasks") >= 5)
              .select("group3", "alpha", (pl.col("zeta") - pl.col("alpha")).alias("e2_share")),
              on="group3", how="inner")
        # a group with no positive-earnings records (unpaid family work) gets the
        # cross-group median so it can still be clustered on its other six features
        .with_columns(pl.col("med_earn").fill_null(pl.col("med_earn").median()).log().alias("log_med_earn"))
        .select("group3", "workers_m", "med_earn", "alpha", "e2_share", "grad_share",
                "female_share", "urban_share", "young_share", "log_med_earn")
        .sort("group3")
    )
    return feats


FEATURES = ["alpha", "e2_share", "grad_share", "female_share",
            "urban_share", "young_share", "log_med_earn"]


def profile_clusters(df: pl.DataFrame, assigned: pl.DataFrame) -> pl.DataFrame:
    """Cluster profiles straight off the pooled unit records — every share, the
    wage bill and the median are survey-weighted over the same worker set."""
    w = df.join(assigned.select("group3", "cluster"), on="group3", how="inner")
    wage_bill_total = float((w["monthly_earnings"] * w["weight"]).sum())
    med = weighted_median_by(w.filter(pl.col("monthly_earnings") > 0),
                             "cluster", "monthly_earnings", "weight", "median_earnings_inr")

    def wshare(cond: pl.Expr) -> pl.Expr:
        return (cond.cast(pl.Float64) * pl.col("weight")).sum() / pl.col("weight").sum()

    prof = (
        w.group_by("cluster")
        .agg(
            pl.col("group3").n_unique().alias("n_groups"),
            (pl.col("weight").sum() / 1e6).alias("workers_m"),
            ((pl.col("alpha") * pl.col("weight")).sum() / pl.col("weight").sum()).alias("alpha"),
            (((pl.col("zeta") - pl.col("alpha")) * pl.col("weight")).sum()
             / pl.col("weight").sum()).alias("e2_share"),
            wshare(pl.col("beta") >= HIGH_EXPOSURE_BETA).alias("high_exposure_share"),
            wshare(pl.col("edu_code").is_in([10, 11, 12, 13])).alias("grad_share"),
            wshare(pl.col("sex_code") == 2).alias("female_share"),
            wshare(pl.col("sector_code") == 2).alias("urban_share"),
            wshare((pl.col("age") >= 18) & (pl.col("age") <= 29)).alias("young_share"),
            ((pl.col("monthly_earnings") * pl.col("weight")).sum() / wage_bill_total)
            .alias("wage_bill_share"),
        )
        .join(med, on="cluster", how="left")
        .sort("alpha", descending=True)
    )
    # exemplars: the three groups with the largest employment in the cluster
    top = (w.group_by("cluster", "group3").agg(pl.col("weight").sum())
           .sort("weight", descending=True)
           .group_by("cluster", maintain_order=True)
           .agg(pl.col("group3").head(3).alias("codes")))
    exemplars = pl.DataFrame({
        "cluster": top["cluster"],
        "exemplars": [", ".join(label(c) for c in codes) for codes in top["codes"].to_list()],
    })
    prof = prof.join(exemplars, on="cluster", how="left")
    return prof.with_columns(pl.Series("name", name_clusters(prof)))


def name_clusters(prof: pl.DataFrame) -> list[str]:
    """Resolve cluster names from the profile, in profile row order.

    k-means labels are arbitrary integers — re-running after any feature or
    data change can permute them — so nothing downstream may hard-code an id.
    The five-world naming rule (only applied when k = 5) reads off the profile:
    the most chat-exposed world is the frontier, the most tooling-exposed of
    what remains is the paperwork layer, then the most graduate-heavy is the
    managerial middle, and the least urban of the last two is agrarian.
    """
    rows = {r["cluster"]: r for r in prof.iter_rows(named=True)}
    order = list(prof["cluster"])
    if prof.height != 5:
        return [f"Cluster {c}" for c in order]
    left = set(rows)

    def take(key: str, largest: bool = True) -> int:
        pick = (max if largest else min)(left, key=lambda c: rows[c][key])
        left.discard(pick)
        return pick

    names = {
        take("alpha"): "Frontier professionals",
        take("e2_share"): "The paperwork layer",
        take("grad_share"): "Managers & teachers",
        take("urban_share", largest=False): "Rural agrarian mass",
    }
    names[left.pop()] = "Urban manual & retail"
    return [names[c] for c in order]


def _bold_max(vals: list[float], fmt) -> list[str]:
    hi = max(vals)
    return [f"**{fmt(v)}**" if v == hi else fmt(v) for v in vals]


def render_table(prof: pl.DataFrame) -> str:
    """White paper section 8b table: 11 attributes x k worlds, columns ordered
    by chat exposure (profile order)."""
    def pct(v: float) -> str:
        return f"{v * 100:.0f}%"

    def dec(v: float) -> str:
        return f"{v:.2f}"

    def rupees(v: float) -> str:
        return f"₹{round(v, -2):,.0f}"

    d = prof.to_dict(as_series=False)
    rows = [
        ("Occupation groups", [str(n) for n in d["n_groups"]]),
        ("**Workers**", [f"{w:.0f}M" for w in d["workers_m"]]),
        ("Chat exposure (α)", _bold_max(d["alpha"], dec)),
        ("Tooling exposure (E2 share)", _bold_max(d["e2_share"], dec)),
        (f"Workers in high-exposure jobs (β ≥ {HIGH_EXPOSURE_BETA})",
         _bold_max(d["high_exposure_share"], pct)),
        ("Graduate share", _bold_max(d["grad_share"], pct)),
        ("Female share", _bold_max(d["female_share"], pct)),
        ("Urban share", _bold_max(d["urban_share"], pct)),
        ("Young (18–29) share", _bold_max(d["young_share"], pct)),
        ("Median monthly earnings", _bold_max(d["median_earnings_inr"], rupees)),
        ("Share of national wage bill", [pct(v) for v in d["wage_bill_share"]]),
        ("Exemplar occupations", list(d["exemplars"])),
    ]
    head = "| | " + " | ".join(d["name"]) + " |"
    rule = "|" + "---|" * (prof.height + 1)
    body = "\n".join(f"| {lab} | " + " | ".join(vals) + " |" for lab, vals in rows)
    note = (
        "\n*Employment-weighted cluster profiles from PLFS 2023-24 unit records "
        "(survey weight = mult/no_qtr). Earnings are the survey-weighted median "
        "monthly earnings of earners in the cluster — salaried + self-employed; "
        "casual daily wages excluded. Wage-bill shares are of the same earnings "
        "concept. All PRELIMINARY per D6. Regenerate with `make typology`; do not "
        "edit by hand.*\n"
    )
    return f"{head}\n{rule}\n{body}\n{note}"


def write_table(md: str) -> None:
    tables = paper_dir() / "whitepaper" / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    (tables / "typology_clusters_PRELIMINARY.md").write_text(md)
    wp = paper_dir() / "whitepaper" / "AI-Exposure-Atlas-WhitePaper.md"
    if not wp.exists():
        return
    text = wp.read_text()
    if BEGIN_MARK not in text or END_MARK not in text:
        print(f"NOTE: no generated block in {wp.name}; table written to tables/ only")
        return
    head, _, rest = text.partition(BEGIN_MARK)
    _, _, tail = rest.partition(END_MARK)
    wp.write_text(f"{head}{BEGIN_MARK}\n{md}{END_MARK}{tail}")
    print(f"spliced cluster table into {wp.name} section 8b")


def main() -> None:
    workers = load_workers()
    feats = build_features(workers)
    X = StandardScaler().fit_transform(feats.select(FEATURES).to_numpy())

    sil = {}
    fits = {}
    for k in range(3, 8):
        km = KMeans(n_clusters=k, n_init=50, random_state=run_seed())
        lab = km.fit_predict(X)
        sil[k] = float(silhouette_score(X, lab))
        fits[k] = lab
    best_k = max(sil, key=sil.get)
    out = feats.with_columns(pl.Series("cluster", fits[best_k]))

    profile = profile_clusters(workers, out)
    out = out.join(profile.select("cluster", "name"), on="cluster", how="left")

    tables = outputs_dir() / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    out.write_parquet(processed_dir() / "occupation_typology_PRELIMINARY.parquet")
    profile.select(
        "cluster", "name", "n_groups", "workers_m",
        *[pl.col(f).round(3) for f in FEATURES if f != "log_med_earn"],
        pl.col("high_exposure_share").round(3),
        pl.col("median_earnings_inr").round(0),
        pl.col("wage_bill_share").round(4),
        "exemplars",
    ).write_csv(tables / "typology_profiles_PRELIMINARY.csv")
    write_table(render_table(profile))

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRELIMINARY per D6",
        "method": f"k-means, standardized features, n_init=50, seed={run_seed()}",
        "silhouette_by_k": {str(k): round(v, 3) for k, v in sil.items()},
        "chosen_k": best_k,
        "features": FEATURES,
        "earnings": "survey-weighted median (weight = mult/no_qtr) of monthly_earnings "
                    "among earners; group medians feed the clustering feature, cluster "
                    "medians are computed on pooled unit records, not averaged from groups",
        "cluster_names": dict(zip(profile["cluster"].to_list(), profile["name"].to_list())),
    }
    (processed_dir() / "occupation_typology_PRELIMINARY.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta["silhouette_by_k"], indent=1), "-> k =", best_k)
    with pl.Config(tbl_cols=14, tbl_width_chars=160):
        print(profile.drop("exemplars"))
    for r in profile.iter_rows(named=True):
        print(f"{r['name']}: {r['exemplars']}")


if __name__ == "__main__":
    main()
