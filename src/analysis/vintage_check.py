"""Vintage check (referee point 2; PRELIMINARY per D6).

For 10 visibly-digitised occupations, scores BOTH the original NCO-2015 task
list and an author-constructed modernised task list
(config/vintage_tasks_v1.yaml) under the frozen rubric via src/llm/score.py
(cached, 3-sample majority vote), and reports the drift
beta(modernised) - beta(original).

This is an assumption exhibit that bounds the description-vintage problem;
the index itself is unchanged. Both variants go through the same scorer, so
the comparison is like-for-like.

Outputs:
  outputs/tables/vintage_check_PRELIMINARY.csv
  outputs/tables/vintage_check_PRELIMINARY.meta.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import polars as pl
import yaml

from atlas_common import REPO_ROOT, outputs_dir, processed_dir
from llm.score import score_task

BW = {"E0": 0.0, "E1": 1.0, "E2": 0.5}


def beta_of(scores: list[str]) -> float:
    usable = [s for s in scores if s in BW]
    return sum(BW[s] for s in usable) / len(usable) if usable else float("nan")


def main() -> None:
    import anthropic

    client = anthropic.Anthropic()
    cfg = yaml.safe_load((REPO_ROOT / "config" / "vintage_tasks_v1.yaml").read_text())
    orig = pl.read_parquet(processed_dir() / "task_statements_full.parquet")
    corpus = pl.read_parquet(processed_dir() / "occupation_index_PRELIMINARY.parquet")

    rows = []
    ties = 0
    for code, spec in cfg["occupations"].items():
        o_tasks = orig.filter(pl.col("nco_code") == code)
        o_scores, m_scores = [], []
        for r in o_tasks.iter_rows(named=True):
            ts = score_task(f"vintage-orig-{r['task_id']}", r["task_text"], client=client)
            ties += ts.tie_escalated
            o_scores.append(ts.score)
        for i, text in enumerate(spec["tasks"]):
            ts = score_task(f"vintage-mod-{code}-t{i:02d}", text, client=client)
            ties += ts.tie_escalated
            m_scores.append(ts.score)
        c = corpus.filter(pl.col("nco_code") == code)
        rows.append({
            "nco_code": code,
            "title": spec["title"],
            "n_tasks_original": len(o_scores),
            "n_tasks_modernised": len(m_scores),
            "beta_original_3s": round(beta_of(o_scores), 3),
            "beta_modernised_3s": round(beta_of(m_scores), 3),
            "beta_corpus_1s": round(float(c["beta"][0]), 3) if c.height else None,
            "drift": round(beta_of(m_scores) - beta_of(o_scores), 3),
        })
        print(rows[-1])

    df = pl.DataFrame(rows)
    df.write_csv(outputs_dir() / "tables" / "vintage_check_PRELIMINARY.csv")
    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRELIMINARY per D6; assumption exhibit (author-constructed modernised task lists)",
        "task_lists": "config/vintage_tasks_v1.yaml",
        "scorer": "src/llm/score.py, frozen rubric, 3-sample majority vote, both variants",
        "ties_escalated": ties,
        "mean_drift": round(float(df["drift"].mean()), 3),
        "mean_beta_original": round(float(df["beta_original_3s"].mean()), 3),
        "mean_beta_modernised": round(float(df["beta_modernised_3s"].mean()), 3),
    }
    (outputs_dir() / "tables" / "vintage_check_PRELIMINARY.meta.json").write_text(
        json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
