"""Occupation-level exposure index from task scores (ANALYSIS_PLAN §2.3).

Aggregations per the Eloundou convention, tasks weighted equally:
    alpha = share of tasks scored E1
    beta  = share E1 + 0.5 * share E2
    zeta  = share E1 + share E2

Levels:
    occupation (8-digit NCO entry)  -> occupation_index_*.parquet
    group3 (3-digit, PLFS merge key) -> group3_index_*.parquet

Gate (Golden Rule 4 / D6): a FINAL build requires the human-validation kappa
gate to have cleared. Until then only PRELIMINARY builds are permitted — they
run on LLM-only scores, carry preliminary=True in every row and PRELIMINARY in
every filename, and may not feed the abstract or paper.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import polars as pl

from atlas_common import REPO_ROOT, load_config, processed_dir, schemas

PRELIM_SCORES = REPO_ROOT / "outputs" / "full_batch_scoring" / "task_scores_full_PRELIMINARY.parquet"


def build(scores: pl.DataFrame, tasks: pl.DataFrame, preliminary: bool) -> dict[str, pl.DataFrame]:
    cfg = load_config()
    scored = scores.filter(pl.col("score").is_in(["E0", "E1", "E2"])).join(
        tasks.select("task_id", "occupation_title"), on="task_id"
    )

    def aggregate(keys: list[str]) -> pl.DataFrame:
        return (
            scored.group_by(keys)
            .agg(
                pl.len().cast(pl.Int64).alias("n_tasks"),
                (pl.col("score") == "E1").mean().alias("alpha"),
                ((pl.col("score") == "E1") + 0.5 * (pl.col("score") == "E2")).mean().alias("beta"),
                pl.col("score").is_in(["E1", "E2"]).mean().alias("zeta"),
            )
            .with_columns(
                pl.lit("E1").alias("variant"),  # NCO-only task base; E1plus needs postings
                pl.lit(scores["rubric_version"][0]).alias("rubric_version"),
                pl.lit(preliminary).alias("preliminary"),
            )
            .sort(keys)
        )

    occ = aggregate(["nco_code", "occupation_title"]).select(
        "nco_code", "occupation_title", "n_tasks", "variant",
        "alpha", "beta", "zeta", "rubric_version", "preliminary",
    )
    grp = aggregate(["group3"])
    return {"occupation": occ, "group3": grp}


def main() -> None:
    cfg = load_config()
    if not PRELIM_SCORES.exists():
        raise SystemExit("No score file found. FINAL builds additionally require the "
                         f"kappa >= {cfg['validation']['min_kappa']} gate (not yet cleared).")

    scores = pl.read_parquet(PRELIM_SCORES)
    preliminary = bool(scores.get_column("preliminary", default=pl.Series([True]))[0])
    if not preliminary:
        raise SystemExit(f"FINAL index build is gated on kappa >= {cfg['validation']['min_kappa']} "
                         "(pilot validation deferred per D6 — not cleared).")

    tasks = pl.read_parquet(processed_dir() / "task_statements_full.parquet")
    out = build(scores, tasks, preliminary=True)
    schemas.occupation_index.validate(out["occupation"], lazy=True)

    tag = "PRELIMINARY"
    occ_path = processed_dir() / f"occupation_index_{tag}.parquet"
    grp_path = processed_dir() / f"group3_index_{tag}.parquet"
    out["occupation"].write_parquet(occ_path)
    out["group3"].write_parquet(grp_path)

    n_total_tasks = tasks.height
    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRELIMINARY per D6 — LLM-only scores, 1 sample/task; NOT for paper/abstract",
        "scores_input": str(PRELIM_SCORES),
        "n_tasks_scored": scores.height,
        "task_coverage": round(scores.height / n_total_tasks, 4),
        "n_occupations": out["occupation"].height,
        "n_groups3": out["group3"].height,
        "groups_with_lt5_tasks": int((out["group3"]["n_tasks"] < 5).sum()),
        "rubric_version": scores["rubric_version"][0],
        "aggregation": "tasks weighted equally (ANALYSIS_PLAN §2.3 baseline)",
    }
    (processed_dir() / f"index_build_{tag}.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
