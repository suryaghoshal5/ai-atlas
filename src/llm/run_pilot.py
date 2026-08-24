"""Run claude-sonnet-4-6 on the 400-task pilot (Sprint 0 kappa proof).

All API traffic goes through llm.score.score_task (Golden Rule 3): cached,
versioned, temperature 0, 3 samples, majority vote, ties escalate to human.

Batch policy (CLAUDE.md): fails if >2% of tasks unresolved; spend is reported
from recorded token usage against the USD 200 budget.
"""

from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import polars as pl

from atlas_common import load_config, processed_dir, schemas
from llm import score as score_mod

WORKERS = 8
# claude-sonnet-4-6 list prices, USD per million tokens (for reporting only)
PRICE_IN, PRICE_OUT = 3.0, 15.0


def main() -> None:
    cfg = load_config()["llm"]
    tasks = pl.read_parquet(processed_dir() / "pilot_tasks.parquet")
    print(f"scoring {tasks.height} tasks with {cfg['model']}, rubric {cfg['rubric_version']}")

    import anthropic

    client = anthropic.Anthropic()

    started = datetime.now(timezone.utc).isoformat()
    results, failures = [], []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {
            ex.submit(score_mod.score_task, r["task_id"], r["task_text"], client): r["task_id"]
            for r in tasks.iter_rows(named=True)
        }
        for n, fut in enumerate(as_completed(futs), 1):
            task_id = futs[fut]
            try:
                results.append(fut.result())
            except Exception as e:  # ScoringError or API-terminal errors
                failures.append(task_id)
                score_mod.log_failure(task_id, f"task-level failure: {e}")
            if n % 50 == 0:
                print(f"  {n}/{tasks.height} done ({len(failures)} failures)")

    fail_rate = len(failures) / tasks.height
    rows = [
        {
            "task_id": r.task_id,
            "rubric_version": r.rubric_version,
            "model": r.model,
            "score": r.score,
            "votes_e0": r.votes.get("E0", 0),
            "votes_e1": r.votes.get("E1", 0),
            "votes_e2": r.votes.get("E2", 0),
            "tie_escalated": r.tie_escalated,
            "scored_at": r.scored_at,
        }
        for r in results
    ]
    out = pl.DataFrame(rows).sort("task_id")
    schemas.task_scores.validate(out, lazy=True)
    out.write_parquet(processed_dir() / "pilot_llm_scores.parquet")

    with sqlite3.connect(score_mod.CACHE_DB) as conn:
        tok_in, tok_out = conn.execute(
            "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) FROM calls"
        ).fetchone()
    cost = tok_in / 1e6 * PRICE_IN + tok_out / 1e6 * PRICE_OUT

    dist = out.group_by("score").len().sort("score")
    meta = {
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "model": cfg["model"],
        "rubric_version": cfg["rubric_version"],
        "n_tasks": tasks.height,
        "n_scored": out.height,
        "n_failures": len(failures),
        "failure_rate": round(fail_rate, 4),
        "n_ties_escalated": int(out["tie_escalated"].sum()),
        "score_distribution": {k: int(v) for k, v in dist.iter_rows()},
        "tokens": {"input": int(tok_in), "output": int(tok_out)},
        "approx_cost_usd": round(cost, 2),
    }
    (processed_dir() / "pilot_llm_scores.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))

    if fail_rate > cfg["batch_fail_threshold"]:
        raise SystemExit(f"BATCH FAILED: {fail_rate:.1%} unresolved > "
                         f"{cfg['batch_fail_threshold']:.0%} threshold")


if __name__ == "__main__":
    main()
