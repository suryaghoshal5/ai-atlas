"""Pilot validation: agreement between Surya's manual scores and the LLM
(Sprint 0 exit gate). Computes Cohen's kappa (unweighted, primary, per
ANALYSIS_PLAN §2.4), the confusion matrix, and a disagreement listing.

Gate: kappa >= 0.7 -> freeze rubric v1. Below -> STOP, revise rubric wording
using the disagreement examples.

Rows excluded from kappa (reported, never silently dropped):
  - LLM ties (no majority verdict; escalated to human by design)
  - blank human scores (should be zero)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import polars as pl

from atlas_common import outputs_dir, processed_dir

LABELS = ["E0", "E1", "E2"]
HUMAN_COL = "human_score_E0_E1_E2"


def cohen_kappa(pairs: pl.DataFrame) -> tuple[float, dict]:
    n = pairs.height
    conf = {(h, m): 0 for h in LABELS for m in LABELS}
    for h, m in pairs.select("human", "llm").iter_rows():
        conf[(h, m)] += 1
    po = sum(conf[(l, l)] for l in LABELS) / n
    pe = sum(
        (sum(conf[(h, m)] for m in LABELS) / n) * (sum(conf[(h2, h)] for h2 in LABELS) / n)
        for h in LABELS
    )
    kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    return kappa, {"po": po, "pe": pe, "confusion": {f"{h}|{m}": v for (h, m), v in conf.items()}}


def main() -> None:
    human = pl.read_csv(processed_dir() / "pilot_scoring_sheet.csv").rename(
        {HUMAN_COL: "human"}
    )
    llm = pl.read_parquet(processed_dir() / "pilot_llm_scores.parquet").rename(
        {"score": "llm"}
    )
    tasks = pl.read_parquet(processed_dir() / "pilot_tasks.parquet")

    human = human.with_columns(pl.col("human").cast(pl.Utf8).str.strip_chars().str.to_uppercase())
    bad = human.filter(~pl.col("human").is_in(LABELS))

    # Alignment guard: the sheet regenerated once (400 -> 392 tasks), which
    # renumbered ids inside 8 occupations. Never trust the id join blindly —
    # verify the scored sheet's task text matches the canonical text, and fall
    # back to a text join if ids have drifted.
    id_check = human.select("task_id", pl.col("task_text").alias("text_h")).join(
        tasks.select("task_id", "task_text"), on="task_id", how="inner"
    )
    mismatched = id_check.filter(
        pl.col("text_h").str.strip_chars() != pl.col("task_text").str.strip_chars()
    ).height
    if mismatched:
        print(f"WARNING: {mismatched} task_ids carry different text (old sheet?) — joining on task text instead")
        human = human.drop("task_id").join(
            tasks.select("task_id", "task_text"), on="task_text", how="inner"
        )
    j = (
        human.select("task_id", "human", "notes")
        .join(llm.select("task_id", "llm", "votes_e0", "votes_e1", "votes_e2", "tie_escalated"), on="task_id", how="inner")
        .join(tasks.select("task_id", "occupation_title", "task_text"), on="task_id")
    )
    ties = j.filter(pl.col("llm") == "TIE")
    usable = j.filter(pl.col("llm").is_in(LABELS) & pl.col("human").is_in(LABELS))

    kappa, detail = cohen_kappa(usable)
    agree = usable.filter(pl.col("human") == pl.col("llm")).height

    out = outputs_dir() / "pilot"
    out.mkdir(parents=True, exist_ok=True)
    disagreements = usable.filter(pl.col("human") != pl.col("llm")).sort("task_id")
    disagreements.write_csv(out / "pilot_disagreements.csv")

    conf_rows = [
        {"human": h, **{f"llm_{m}": detail["confusion"][f"{h}|{m}"] for m in LABELS}}
        for h in LABELS
    ]
    pl.DataFrame(conf_rows).write_csv(out / "pilot_confusion_matrix.csv")

    report = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "n_tasks_joined": j.height,
        "n_usable_pairs": usable.height,
        "n_llm_ties_excluded": ties.height,
        "n_invalid_human_labels": bad.height,
        "percent_agreement": round(agree / usable.height, 4),
        "cohens_kappa_unweighted": round(kappa, 4),
        "expected_agreement_pe": round(detail["pe"], 4),
        "n_disagreements": disagreements.height,
        "gate": "PASS (freeze rubric v1)" if kappa >= 0.7 else "FAIL (STOP: revise rubric)",
        "human_distribution": dict(usable.group_by("human").len().sort("human").iter_rows()),
        "llm_distribution": dict(usable.group_by("llm").len().sort("llm").iter_rows()),
    }
    (out / "pilot_kappa_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if bad.height:
        print("\nINVALID human labels (fix and re-run):")
        for r in bad.head(10).iter_rows(named=True):
            print(" -", r["task_id"], repr(r["human"]))


if __name__ == "__main__":
    main()
