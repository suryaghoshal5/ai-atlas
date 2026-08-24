"""Single entry point for ALL LLM classification calls (Golden Rule 3).

No ad-hoc API calls anywhere else in the codebase. Every call is:
  - cached on (model, rubric_version, prompt_hash, task_text, sample_idx)
  - versioned via config/config.yaml rubric_version
  - deterministic in intent: temperature 0, majority vote over N samples

Failure policy (CLAUDE.md):
  - malformed/refused output -> retry once with stricter system prompt
  - second failure -> append task_id to logs/score_failures.csv, continue
  - batch fails if >2% of tasks unresolved
  - cumulative spend beyond budget_usd -> pause and require confirmation

The rubric prompt itself lives in config/rubric_v*.md. The scoring rubric is
DRAFT until the 50-occupation pilot clears the kappa gate; do not run full-corpus
scoring on a draft rubric.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from atlas_common import REPO_ROOT, load_config, logs_dir

CACHE_DB = REPO_ROOT / "cache" / "llm_scores.sqlite"
VALID_SCORES = ("E0", "E1", "E2")


@dataclass
class TaskScore:
    task_id: str
    score: str  # E0 | E1 | E2, or "TIE" pending human escalation
    votes: Counter
    tie_escalated: bool
    rubric_version: str
    model: str
    scored_at: str


def _cache_conn() -> sqlite3.Connection:
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_DB, timeout=30)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS calls (
            key TEXT PRIMARY KEY,
            model TEXT, rubric_version TEXT, task_id TEXT, sample_idx INTEGER,
            response TEXT, input_tokens INTEGER, output_tokens INTEGER,
            created_at TEXT
        )"""
    )
    return conn


def _cache_key(model: str, rubric_version: str, prompt: str, task_text: str, sample_idx: int) -> str:
    h = hashlib.sha256()
    h.update(json.dumps([model, rubric_version, prompt, task_text, sample_idx]).encode())
    return h.hexdigest()


def load_rubric_prompt(rubric_version: str) -> str:
    path = REPO_ROOT / "config" / f"rubric_v{rubric_version}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Rubric prompt not found: {path}. The rubric is authored/frozen via the "
            "pilot process (ANALYSIS_PLAN.md §2.2), not generated at runtime."
        )
    return path.read_text()


def log_failure(task_id: str, reason: str) -> None:
    logs_dir().mkdir(parents=True, exist_ok=True)
    path = logs_dir() / "score_failures.csv"
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["task_id", "reason", "at"])
        w.writerow([task_id, reason, datetime.now(timezone.utc).isoformat()])


def score_task(task_id: str, task_text: str, client=None) -> TaskScore:
    """Score one task statement: N cached samples at temperature 0, majority vote.

    `client` is an anthropic.Anthropic instance; injected for testability.
    Ties are NOT resolved here — they escalate to human review per the plan.
    """
    cfg = load_config()["llm"]
    rubric_version = cfg["rubric_version"]
    prompt = load_rubric_prompt(rubric_version)

    votes: Counter = Counter()
    conn = _cache_conn()

    def cached_call(sample_idx: int, system_prompt: str) -> str:
        key = _cache_key(cfg["model"], rubric_version, system_prompt, task_text, sample_idx)
        row = conn.execute("SELECT response FROM calls WHERE key = ?", (key,)).fetchone()
        if row is not None:
            return row[0]
        raw, tok_in, tok_out = _call_api(client, cfg, system_prompt, task_text)
        conn.execute(
            "INSERT INTO calls (key, model, rubric_version, task_id, sample_idx, response, "
            "input_tokens, output_tokens, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (key, cfg["model"], rubric_version, task_id, sample_idx, raw, tok_in, tok_out,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return raw

    STRICT_SUFFIX = (
        "\n\nIMPORTANT: Your final line MUST be exactly 'SCORE: E0', 'SCORE: E1' "
        "or 'SCORE: E2'. No other final line is acceptable."
    )
    for i in range(cfg["samples_per_task"]):
        raw = cached_call(i, prompt)
        parsed = _parse_score(raw)
        if parsed is None:
            # failure policy: retry once with stricter system prompt, then log
            raw = cached_call(100 + i, prompt + STRICT_SUFFIX)
            parsed = _parse_score(raw)
        if parsed is None:
            log_failure(task_id, f"unparseable sample {i} after strict retry: {raw[:200]}")
            continue
        votes[parsed] += 1
    conn.close()

    if not votes:
        raise ScoringError(f"all samples unparseable for task {task_id}")

    top = votes.most_common(2)
    tie = len(top) > 1 and top[0][1] == top[1][1]
    return TaskScore(
        task_id=task_id,
        score="TIE" if tie else top[0][0],
        votes=votes,
        tie_escalated=tie,
        rubric_version=rubric_version,
        model=cfg["model"],
        scored_at=datetime.now(timezone.utc).isoformat(),
    )


class ScoringError(RuntimeError):
    pass


def _call_api(client, cfg: dict, prompt: str, task_text: str) -> tuple[str, int, int]:
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    msg = client.messages.create(
        model=cfg["model"],
        max_tokens=200,
        temperature=cfg["temperature"],
        system=prompt,
        messages=[{"role": "user", "content": task_text}],
    )
    usage = getattr(msg, "usage", None)
    text = next((b.text for b in msg.content if getattr(b, "type", "") == "text"), "")
    return (
        text,
        getattr(usage, "input_tokens", 0) or 0,
        getattr(usage, "output_tokens", 0) or 0,
    )


def _parse_score(raw: str) -> str | None:
    """Extract E0/E1/E2 from a model response. Expects the rubric to instruct
    the model to end with a line `SCORE: E<n>`."""
    for line in reversed(raw.strip().splitlines()):
        line = line.strip().upper()
        if line.startswith("SCORE:"):
            candidate = line.removeprefix("SCORE:").strip()
            if candidate in VALID_SCORES:
                return candidate
    return None


def main() -> None:
    raise SystemExit(
        "Full-corpus scoring is gated: the rubric is still draft (pilot kappa gate "
        "not cleared). Run the pilot via scripts once NCO task statements exist."
    )


if __name__ == "__main__":
    main()
