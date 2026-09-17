"""Human-validation rating sheets (Golden Rule 4, D6).

Writes to outputs/validation/:
    rating_sheet_v1.csv          the validation sample: three blind rater columns
    rating_sheet_v1_key.csv      task_id -> LLM label and sampling stratum (keep
                                 away from raters until the sheet is complete)
    rating_sheet_full_corpus.csv every NCO Vol II task statement, same columns,
                                 NCO order, for a full pass if ever wanted
    RATING_MANUAL.md             rater instructions with the rubric verbatim
    validation_sheet.meta.json   counts, seed, inputs

Sample design (seed = ATLAS_RUN_SEED, default 42):
    * universe: the 18,622 parsed statements minus the 392 pilot tasks that
      already carry two rounds of human labels;
    * strata by the full-batch LLM label: N_PER_STRATUM each of E0, E1, E2,
      uniform random within stratum, so the rare labels are represented (a
      simple random draw of 400 would hold ~40 E1 and ~25 E2);
    * plus every task the batch left unresolved (no label), which needs a
      human score regardless;
    * rows shuffled so the stratum cannot be read off the order.
Rater columns carry no LLM information: the sheet is blind by construction.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone

import polars as pl
import yaml

from atlas_common import REPO_ROOT, load_config, processed_dir, outputs_dir, run_seed

OUT = outputs_dir() / "validation"
SCORES = REPO_ROOT / "outputs" / "full_batch_scoring" / "task_scores_full_PRELIMINARY.parquet"
PILOT = REPO_ROOT / "outputs" / "pilot" / "pilot_scoring_sheet.csv"
TITLES = REPO_ROOT / "config" / "nco2015_titles.yaml"
MANUAL_TEMPLATE = REPO_ROOT / "src" / "analysis" / "rating_manual_template.md"
N_PER_STRATUM = 200
RATERS = 3

COLS = ["seq", "task_id", "nco_code", "occupation_title", "group3", "group_title",
        "family_title", "task_text"]


def rater_cols() -> list[str]:
    return [f"rating_{i}" for i in range(1, RATERS + 1)] + [f"notes_{i}" for i in range(1, RATERS + 1)]


def corpus() -> pl.DataFrame:
    t = yaml.safe_load(TITLES.read_text())
    groups = {str(k): v for k, v in t["groups"].items()}
    fams = {str(k): v for k, v in t["families"].items()}
    tasks = pl.read_parquet(processed_dir() / "task_statements_full.parquet")
    scores = pl.read_parquet(SCORES).select("task_id", pl.col("score").alias("llm_label"))
    return (tasks.join(scores, on="task_id", how="left")
            .with_columns(
                pl.col("group3").replace_strict(groups, default=None).alias("group_title"),
                pl.col("nco_code").str.slice(0, 4).replace_strict(fams, default=None).alias("family_title"),
            )
            .sort("task_id"))


def draw_sample(df: pl.DataFrame, seed: int) -> pl.DataFrame:
    pilot_ids = set(pl.read_csv(PILOT)["task_id"].to_list())
    pool = df.filter(~pl.col("task_id").is_in(pilot_ids))
    rng = random.Random(seed)
    parts = []
    for lab in ("E0", "E1", "E2"):
        ids = sorted(pool.filter(pl.col("llm_label") == lab)["task_id"].to_list())
        picked = rng.sample(ids, min(N_PER_STRATUM, len(ids)))
        parts.append(pool.filter(pl.col("task_id").is_in(picked)).with_columns(pl.lit(lab).alias("stratum")))
    parts.append(pool.filter(pl.col("llm_label").is_null()).with_columns(pl.lit("unresolved").alias("stratum")))
    sample = pl.concat(parts)
    order = list(range(sample.height))
    rng.shuffle(order)
    return (sample.with_columns(pl.Series("shuffle", order)).sort("shuffle")
            .with_columns((pl.int_range(1, sample.height + 1)).alias("seq")).drop("shuffle"))


def blank_sheet(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(COLS).with_columns([pl.lit("").alias(c) for c in rater_cols()])


def write_manual(meta: dict) -> None:
    cfg = load_config()
    rubric_path = REPO_ROOT / "config" / f"rubric_v{cfg['llm']['rubric_version']}.md"
    rubric = rubric_path.read_text()
    rubric = rubric[rubric.index("You are scoring"):]  # drop the HTML status comment
    body = (MANUAL_TEMPLATE.read_text()
            .replace("{{RUBRIC_VERSION}}", cfg["llm"]["rubric_version"])
            .replace("{{N_SAMPLE}}", str(meta["n_sample"]))
            .replace("{{N_PER_STRATUM}}", str(N_PER_STRATUM))
            .replace("{{N_UNRESOLVED}}", str(meta["n_unresolved"]))
            .replace("{{N_FULL}}", str(meta["n_full_corpus"]))
            .replace("{{MIN_KAPPA}}", str(cfg["validation"]["min_kappa"]))
            .replace("{{BUILT}}", meta["built_at"])
            .replace("{{RUBRIC_VERBATIM}}", rubric.strip()))
    (OUT / "RATING_MANUAL.md").write_text(body)


def main() -> None:
    seed = run_seed()
    OUT.mkdir(parents=True, exist_ok=True)
    df = corpus()
    sample = draw_sample(df, seed)

    blank_sheet(sample).write_csv(OUT / "rating_sheet_v1.csv")
    sample.select("seq", "task_id", "llm_label", "stratum").write_csv(OUT / "rating_sheet_v1_key.csv")
    blank_sheet(df.with_columns(pl.int_range(1, df.height + 1).alias("seq"))).write_csv(
        OUT / "rating_sheet_full_corpus.csv")

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "rubric_version": load_config()["llm"]["rubric_version"],
        "n_full_corpus": df.height,
        "n_pilot_excluded": int(pl.read_csv(PILOT).height),
        "n_per_stratum": N_PER_STRATUM,
        "strata": sample.group_by("stratum").len().sort("stratum").to_dicts(),
        "n_sample": sample.height,
        "n_unresolved": int((sample["stratum"] == "unresolved").sum()),
        "raters": RATERS,
        "inputs": ["data/processed/task_statements_full.parquet",
                   str(SCORES.relative_to(REPO_ROOT)), str(PILOT.relative_to(REPO_ROOT))],
    }
    write_manual(meta)
    (OUT / "validation_sheet.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
