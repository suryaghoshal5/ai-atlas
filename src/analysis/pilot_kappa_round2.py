"""Pilot validation round 2 (rubric v0.2-draft).

Human vector = v0.1 labels for the 330 uncontested tasks + v0.2 re-scores for
the 62 contested tasks (55 round-1 disagreements + 7 hedged labels).
LLM vector = fresh v0.2 run (pilot_llm_scores.parquet, rubric 0.2-draft).
Reuses the kappa/confusion machinery from analysis.pilot_kappa.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import polars as pl

from analysis.pilot_kappa import LABELS, cohen_kappa
from atlas_common import outputs_dir, processed_dir

HUMAN_COL = "human_score_E0_E1_E2"
RESCORE_COL = "human_score_v02_E0_E1_E2"


def main() -> None:
    base = (
        pl.read_csv(processed_dir() / "pilot_scoring_sheet.csv")
        .select("task_id", pl.col(HUMAN_COL).cast(pl.Utf8).str.strip_chars().str.to_uppercase().alias("human"))
    )
    # Surya's round-2 labels live in his edited copy of the round-1
    # disagreements file (`human` column revised under rubric v0.2); the
    # rescore sheet remains a secondary source for the rows not in that file
    # (the 7 round-1 hedges).
    scored_disagreements = (
        pl.read_csv(processed_dir() / "pilot_disagreements.csv")
        .select("task_id", pl.col("human").cast(pl.Utf8).str.strip_chars().str.to_uppercase().alias("human_d"))
    )
    sheet = (
        pl.read_csv(outputs_dir() / "pilot" / "pilot_rescore_sheet_v02.csv")
        .select("task_id", pl.col(RESCORE_COL).cast(pl.Utf8).str.strip_chars().str.to_uppercase().alias("human_s"))
    )
    rescore = (
        sheet.join(scored_disagreements, on="task_id", how="full", coalesce=True)
        .with_columns(pl.coalesce(pl.col("human_d"), pl.col("human_s")).alias("human_v02"))
        .select("task_id", "human_v02")
    )
    blank = rescore.filter(~pl.col("human_v02").is_in(LABELS))
    if blank.height:
        print(f"WARNING: {blank.height} re-score rows blank/invalid (excluded):")
        for r in blank.iter_rows(named=True):
            print(" -", r["task_id"], repr(r["human_v02"]))
    # invalid/blank re-scores must not clobber base labels in the coalesce
    rescore = rescore.with_columns(
        pl.when(pl.col("human_v02").is_in(LABELS)).then(pl.col("human_v02")).otherwise(None).alias("human_v02")
    )

    human = (
        base.join(rescore, on="task_id", how="left")
        .with_columns(pl.coalesce(pl.col("human_v02"), pl.col("human")).alias("human"))
        .with_columns(pl.col("human_v02").is_not_null().alias("rescored"))
    )
    llm = pl.read_parquet(processed_dir() / "pilot_llm_scores.parquet").rename({"score": "llm"})
    assert llm["rubric_version"][0] == "0.2-draft", "LLM scores are not the v0.2 run"
    tasks = pl.read_parquet(processed_dir() / "pilot_tasks.parquet")

    j = (
        human.join(llm.select("task_id", "llm", "tie_escalated"), on="task_id")
        .join(tasks.select("task_id", "occupation_title", "task_text"), on="task_id")
    )
    usable = j.filter(pl.col("llm").is_in(LABELS) & pl.col("human").is_in(LABELS))
    ties = j.filter(pl.col("llm") == "TIE")

    kappa, detail = cohen_kappa(usable)
    agree = usable.filter(pl.col("human") == pl.col("llm")).height
    out = outputs_dir() / "pilot"
    disagreements = usable.filter(pl.col("human") != pl.col("llm")).sort("task_id")
    disagreements.write_csv(out / "pilot_disagreements_round2.csv")
    conf_rows = [
        {"human": h, **{f"llm_{m}": detail["confusion"][f"{h}|{m}"] for m in LABELS}}
        for h in LABELS
    ]
    pl.DataFrame(conf_rows).write_csv(out / "pilot_confusion_matrix_round2.csv")

    report = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "round": 2,
        "rubric_version": "0.2-draft",
        "n_usable_pairs": usable.height,
        "n_rescored_rows_used": int(usable["rescored"].sum()),
        "n_llm_ties_excluded": ties.height,
        "n_blank_rescores": blank.height,
        "percent_agreement": round(agree / usable.height, 4),
        "cohens_kappa_unweighted": round(kappa, 4),
        "expected_agreement_pe": round(detail["pe"], 4),
        "n_disagreements": disagreements.height,
        "gate": "PASS (freeze rubric v1)" if kappa >= 0.7 else "FAIL (STOP: revise again)",
        "human_distribution": dict(usable.group_by("human").len().sort("human").iter_rows()),
        "llm_distribution": dict(usable.group_by("llm").len().sort("llm").iter_rows()),
        "note": "human vector = v0.1 labels for uncontested tasks + v0.2 re-scores for 62 contested; "
                "paper-grade validation is the fresh 200-task subsample under the frozen rubric (Golden Rule 4)",
    }
    (out / "pilot_kappa_report_round2.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
