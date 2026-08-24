"""PRELIMINARY full-corpus scoring: Sonnet 4.6, 1 sample/task, Batch API.

Per D6 (vault CLAUDE.md): kappa gate deferred; outputs are PRELIMINARY and may
not enter the paper. Protocol deviation (1 sample instead of 3) applies to this
preliminary pass only; the paper-grade run adds samples 1-2 and majority-votes.

Cost controls (Surya, Aug 10): Batch API (50% rates), rubric block cached,
HARD PAUSE if cumulative spend would approach USD 80. Cumulative spend prior
to this run: $17.80 (pilot v0.1 + v0.2 live runs).

Cache reuse: any (task_text, sample 0) already scored under rubric 0.2-draft
(the 392 pilot tasks) is served from the local sqlite cache, not re-billed.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime, timezone

import polars as pl
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from atlas_common import load_config, outputs_dir, processed_dir
from llm import score as score_mod

OUT_DIR = outputs_dir() / "full_batch_scoring"

PRIOR_SPEND_USD = 17.80
HARD_CAP_USD = 80.0
# claude-sonnet-4-6 Batch API rates, USD per MTok
RATE_IN, RATE_OUT, RATE_CACHE_WRITE, RATE_CACHE_READ = 1.50, 7.50, 1.875, 0.15
MAX_BATCH_REQUESTS = 10_000

STATE = OUT_DIR / "full_batch_state.json"


def safe_id(task_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", task_id)


def main(wave_limit: int | None = None) -> None:
    cfg = load_config()["llm"]
    assert cfg["model"] == "claude-sonnet-4-6"
    rubric = score_mod.load_rubric_prompt(cfg["rubric_version"])
    tasks = pl.read_parquet(processed_dir() / "task_statements_full.parquet")

    # skip tasks whose sample-0 call is already in the local cache
    conn = sqlite3.connect(score_mod.CACHE_DB)
    todo, cached = [], 0
    for r in tasks.iter_rows(named=True):
        key = score_mod._cache_key(cfg["model"], cfg["rubric_version"], rubric, r["task_text"], 0)
        if conn.execute("SELECT 1 FROM calls WHERE key = ?", (key,)).fetchone():
            cached += 1
        else:
            todo.append(r)
    conn.close()

    # cumulative spend so far: prior live runs + any earlier ingested waves
    prior = PRIOR_SPEND_USD
    meta_path = OUT_DIR / "task_scores_full_PRELIMINARY.meta.json"
    if meta_path.exists():
        prior = json.loads(meta_path.read_text()).get("cumulative_spend_usd", prior)

    if wave_limit:
        todo = todo[:wave_limit]

    # worst-case pre-submission budget check (zero cache hits assumed)
    est_in = len(todo) * (1650 / 1e6) * RATE_IN
    est_out = len(todo) * (130 / 1e6) * RATE_OUT
    worst = est_in + est_out
    print(f"tasks: {tasks.height} | cached (free): {cached} | to submit this wave: {len(todo)}")
    print(f"worst-case cost: ${worst:.2f} | cumulative worst case: ${prior + worst:.2f} (cap ${HARD_CAP_USD})")
    if prior + worst > HARD_CAP_USD:
        raise SystemExit("HARD PAUSE: worst-case estimate exceeds the cap. Not submitting.")

    import anthropic

    client = anthropic.Anthropic()
    system_block = [{"type": "text", "text": rubric, "cache_control": {"type": "ephemeral"}}]
    id_map = {safe_id(r["task_id"]): r["task_id"] for r in todo}

    batch_ids = []
    for start in range(0, len(todo), MAX_BATCH_REQUESTS):
        chunk = todo[start : start + MAX_BATCH_REQUESTS]
        requests = [
            Request(
                custom_id=safe_id(r["task_id"]),
                params=MessageCreateParamsNonStreaming(
                    model=cfg["model"],
                    max_tokens=200,
                    temperature=cfg["temperature"],
                    system=system_block,
                    messages=[{"role": "user", "content": r["task_text"]}],
                ),
            )
            for r in chunk
        ]
        batch = client.messages.batches.create(requests=requests)
        batch_ids.append(batch.id)
        print(f"submitted batch {batch.id} ({len(requests)} requests)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "batch_ids": batch_ids,
        "id_map": id_map,
        "n_cached": cached,
        "rubric_version": cfg["rubric_version"],
        "prior_spend_usd": PRIOR_SPEND_USD,
    }))

    # poll until all batches end
    pending = set(batch_ids)
    while pending:
        time.sleep(120)
        for bid in list(pending):
            b = client.messages.batches.retrieve(bid)
            if b.processing_status == "ended":
                pending.discard(bid)
                print(f"{bid}: ended ({b.request_counts.succeeded} ok, {b.request_counts.errored} err)")
            else:
                print(f"{bid}: {b.processing_status}, processing={b.request_counts.processing}")

    ingest(client, batch_ids, id_map, cfg, rubric, tasks, cached, prior)


def ingest(client, batch_ids, id_map, cfg, rubric, tasks, n_cached, prior_spend) -> None:
    conn = sqlite3.connect(score_mod.CACHE_DB, timeout=30)
    tok = {"in": 0, "out": 0, "cw": 0, "cr": 0}
    n_ok = n_err = 0
    text_by_id = {r["task_id"]: r["task_text"] for r in tasks.iter_rows(named=True)}
    for bid in batch_ids:
        for result in client.messages.batches.results(bid):
            task_id = id_map[result.custom_id]
            if result.result.type != "succeeded":
                n_err += 1
                score_mod.log_failure(task_id, f"batch result: {result.result.type}")
                continue
            msg = result.result.message
            raw = next((b.text for b in msg.content if b.type == "text"), "")
            u = msg.usage
            tok["in"] += u.input_tokens or 0
            tok["out"] += u.output_tokens or 0
            tok["cw"] += getattr(u, "cache_creation_input_tokens", 0) or 0
            tok["cr"] += getattr(u, "cache_read_input_tokens", 0) or 0
            key = score_mod._cache_key(cfg["model"], cfg["rubric_version"], rubric, text_by_id[task_id], 0)
            conn.execute(
                "INSERT OR REPLACE INTO calls (key, model, rubric_version, task_id, sample_idx, "
                "response, input_tokens, output_tokens, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (key, cfg["model"], cfg["rubric_version"], task_id, 0, raw,
                 u.input_tokens or 0, u.output_tokens or 0,
                 datetime.now(timezone.utc).isoformat()),
            )
            n_ok += 1
    conn.commit()

    cost = (tok["in"] * RATE_IN + tok["out"] * RATE_OUT
            + tok["cw"] * RATE_CACHE_WRITE + tok["cr"] * RATE_CACHE_READ) / 1e6
    # assemble full preliminary scores from the cache (batch + pilot sample-0)
    rows = []
    for r in tasks.iter_rows(named=True):
        key = score_mod._cache_key(cfg["model"], cfg["rubric_version"], rubric, r["task_text"], 0)
        row = conn.execute("SELECT response FROM calls WHERE key = ?", (key,)).fetchone()
        if row is None:
            continue
        parsed = score_mod._parse_score(row[0])
        if parsed is None:
            score_mod.log_failure(r["task_id"], "batch sample unparseable")
            continue
        rows.append({"task_id": r["task_id"], "nco_code": r["nco_code"], "group3": r["group3"],
                     "score": parsed, "rubric_version": cfg["rubric_version"],
                     "model": cfg["model"], "n_samples": 1, "preliminary": True})
    conn.close()
    out = pl.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_parquet(OUT_DIR / "task_scores_full_PRELIMINARY.parquet")

    meta = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "protocol": "1 sample/task, temperature 0, Batch API — PRELIMINARY per D6",
        "n_tasks": tasks.height, "n_scored": out.height,
        "n_from_pilot_cache": n_cached, "n_batch_ok": n_ok, "n_batch_errors": n_err,
        "tokens": tok, "batch_cost_usd": round(cost, 2),
        "cumulative_spend_usd": round(prior_spend + cost, 2),
        "score_distribution": dict(out.group_by("score").len().sort("score").iter_rows()),
    }
    (OUT_DIR / "task_scores_full_PRELIMINARY.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


def harvest() -> None:
    """Collect results for batches already submitted (per the state file),
    without submitting anything new. Safe to run after a restart or crash;
    waits for still-processing batches."""
    import anthropic

    state = json.loads(STATE.read_text())
    cfg = load_config()["llm"]
    rubric = score_mod.load_rubric_prompt(state["rubric_version"])
    tasks = pl.read_parquet(processed_dir() / "task_statements_full.parquet")
    client = anthropic.Anthropic()

    pending = set(state["batch_ids"])
    while pending:
        for bid in list(pending):
            b = client.messages.batches.retrieve(bid)
            if b.processing_status == "ended":
                pending.discard(bid)
                print(f"{bid}: ended ({b.request_counts.succeeded} ok, {b.request_counts.errored} err)")
            else:
                print(f"{bid}: {b.processing_status}, processing={b.request_counts.processing}")
        if pending:
            time.sleep(120)

    ingest(client, state["batch_ids"], state["id_map"], cfg, rubric, tasks,
           state["n_cached"], state["prior_spend_usd"])


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "harvest":
        harvest()
    else:
        main(wave_limit=int(sys.argv[1]) if len(sys.argv) > 1 else None)
