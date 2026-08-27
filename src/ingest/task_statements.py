"""Full-corpus task statements — the LLM scoring input, and the spine of the
task master table.

`task_statements_full.parquet` was until now built ad hoc: the full batch run
(llm.run_full_batch) and the index build both read it, but nothing in the repo
produced it, so the scored corpus could not be reconstructed from the raw PDFs
(Golden Rule 1). This module is that missing step.

Enumeration is identical to the pilot (ingest.pilot_select): each Vol II
entry's description is sentence-split by ingest.nco.split_tasks and numbered
within the occupation, so

    task_id = f"{nco_code}-t{i:02d}"

is stable as long as the parsed description is. If a re-parse ever changes the
splitting, task_ids drift out from under the score cache — so the build hard
fails when an already-scored task_id is no longer produced.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import polars as pl

from atlas_common import outputs_dir, processed_dir
from ingest.nco import split_tasks

SCORES = outputs_dir() / "full_batch_scoring" / "task_scores_full_PRELIMINARY.parquet"


def build(entries: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for r in entries.iter_rows(named=True):
        for i, task in enumerate(split_tasks(r["description"], r["occupation_title"]), 1):
            rows.append({
                "nco_code": r["nco_code"],
                "family": r["family"],
                "group3": r["group3"],
                "occupation_title": r["occupation_title"],
                "task_id": f"{r['nco_code']}-t{i:02d}",
                "task_text": task,
                "source": r["source"],
            })
    return pl.DataFrame(rows).sort("task_id")


def check_against_scored(tasks: pl.DataFrame) -> int:
    """Every task_id already scored must still be produced by this build."""
    if not SCORES.exists():
        return 0
    scored = set(pl.read_parquet(SCORES)["task_id"].to_list())
    missing = sorted(scored - set(tasks["task_id"].to_list()))
    if missing:
        raise SystemExit(
            f"STOP: {len(missing)} scored task_ids are no longer produced by the "
            f"parser — the scored corpus cannot be reconstructed. Examples: "
            f"{missing[:5]}. Bisect ingest.nco before rebuilding."
        )
    return len(scored)


def main() -> None:
    entries = pl.read_parquet(processed_dir() / "nco_entries_vol2.parquet")
    tasks = build(entries)
    n_scored = check_against_scored(tasks)

    path = processed_dir() / "task_statements_full.parquet"
    tasks.write_parquet(path)
    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "n_tasks": tasks.height,
        "n_occupations": tasks["nco_code"].n_unique(),
        "n_groups3": tasks["group3"].n_unique(),
        "scored_task_ids_covered": n_scored,
        "inputs": ["data/processed/nco_entries_vol2.parquet"],
        "task_id_rule": "{nco_code}-t{i:02d}, i over ingest.nco.split_tasks output",
    }
    (processed_dir() / "task_statements_full.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
