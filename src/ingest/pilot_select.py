"""Select the 50-occupation pilot set for the manual rubric proof (Sprint 0).

Selection is fully deterministic:
  1. Employment share per 3-digit NCO group from PLFS 2023-24 (principal usual
     status employed, weight = mult / no_qtr).
  2. 50 slots allocated across 1-digit divisions by largest-remainder on
     employment share (every division with parsed NCO content gets >= 1 slot).
  3. Within a division, slots go to the largest 3-digit groups by employment —
     one occupation per group (maximises coverage breadth).
  4. Within a group: the family with the most parsed entries (richest task
     content, tie -> lowest code); within the family, the .0100 archetype entry
     if present, else the lowest suffix.

Outputs:
  data/processed/pilot_tasks.parquet        (schema-validated task statements)
  data/processed/pilot_selection.meta.json  (selection audit trail)
  outputs/pilot/pilot_scoring_sheet.csv     (Surya's manual-scoring sheet)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import polars as pl

from atlas_common import outputs_dir, processed_dir, raw_dir, schemas
from ingest.nco import split_tasks

EMPLOYED_PAS = [11, 12, 21, 31, 41, 51]
N_PILOT = 50


def employment_shares() -> pl.DataFrame:
    perv1 = pl.scan_csv(
        raw_dir() / "plfs" / "plfs_2023-24_jul-jun" / "csv" / "perv1.csv",
        infer_schema_length=10000,
    )
    emp = (
        perv1.filter(pl.col("b5pt1q3_perv1").is_in(EMPLOYED_PAS))
        .select(
            pl.col("b5pt1q6_perv1").cast(pl.Utf8).str.zfill(3).alias("group3"),
            (pl.col("mult_perv1") / pl.col("no_qtr_perv1")).alias("w"),
        )
        .group_by("group3")
        .agg(pl.col("w").sum())
        .collect()
    )
    return emp.with_columns(
        (pl.col("w") / emp["w"].sum()).alias("share"),
        pl.col("group3").str.slice(0, 1).alias("division"),
    )


def allocate_slots(
    shares_by_div: dict[str, float], caps: dict[str, int], n: int
) -> dict[str, int]:
    """Largest-remainder allocation with a minimum of 1 slot per division and a
    cap at the number of distinct 3-digit groups the division actually has
    (one occupation per group). Excess flows to under-quota divisions."""
    divisions = sorted(shares_by_div)
    n = min(n, sum(caps[d] for d in divisions))
    quotas = {d: shares_by_div[d] * n for d in divisions}
    slots = {d: min(caps[d], max(1, int(quotas[d]))) for d in divisions}
    while sum(slots.values()) > n:  # min-1 guarantee may overshoot
        d = max((d for d in divisions if slots[d] > 1), key=lambda d: slots[d] - quotas[d])
        slots[d] -= 1
    while sum(slots.values()) < n:
        eligible = [d for d in divisions if slots[d] < caps[d]]
        d = max(eligible, key=lambda d: quotas[d] - slots[d])
        slots[d] += 1
    return slots


def select_pilot() -> tuple[pl.DataFrame, dict]:
    entries = pl.read_parquet(processed_dir() / "nco_entries_vol2.parquet")
    emp = employment_shares()

    covered = emp.filter(pl.col("group3").is_in(entries["group3"].unique().to_list()))
    div_share = {
        d: s
        for d, s in covered.group_by("division")
        .agg(pl.col("share").sum())
        .iter_rows()
    }
    caps = {d: c for d, c in covered.group_by("division").len().iter_rows()}
    slots = allocate_slots(div_share, caps, N_PILOT)

    picked_groups: list[dict] = []
    for div, k in sorted(slots.items()):
        top = (
            covered.filter(pl.col("division") == div)
            .sort("share", descending=True)
            .head(k)
        )
        picked_groups.extend(top.iter_rows(named=True))

    picks = []
    for g in picked_groups:
        fam_counts = (
            entries.filter(pl.col("group3") == g["group3"])
            .group_by("family")
            .len()
            .sort(["len", "family"], descending=[True, False])
        )
        family = fam_counts["family"][0]
        fam_entries = entries.filter(pl.col("family") == family).sort("nco_code")
        archetype = fam_entries.filter(pl.col("nco_code").str.ends_with(".0100"))
        row = (archetype if archetype.height else fam_entries).row(0, named=True)
        row["employment_share"] = g["share"]
        picks.append(row)
    return pl.DataFrame(picks), slots


def main() -> None:
    picks, slots = select_pilot()

    task_rows = []
    for r in picks.iter_rows(named=True):
        for i, task in enumerate(split_tasks(r["description"], r["occupation_title"]), 1):
            task_rows.append(
                {
                    "nco_code": r["nco_code"],
                    "group3": r["group3"],
                    "occupation_title": r["occupation_title"],
                    "task_id": f"{r['nco_code']}-t{i:02d}",
                    "task_text": task,
                    "source": r["source"],
                }
            )
    tasks = pl.DataFrame(task_rows)
    schemas.pilot_tasks.validate(tasks, lazy=True)
    tasks.write_parquet(processed_dir() / "pilot_tasks.parquet")

    sheet_dir = outputs_dir() / "pilot"
    sheet_dir.mkdir(parents=True, exist_ok=True)
    tasks.select(
        "task_id", "group3", "occupation_title", "task_text"
    ).with_columns(
        pl.lit("").alias("human_score_E0_E1_E2"), pl.lit("").alias("notes")
    ).write_csv(sheet_dir / "pilot_scoring_sheet.csv")

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "n_occupations": picks.height,
        "n_tasks": tasks.height,
        "slots_by_division": slots,
        "employment_share_covered": round(float(picks["employment_share"].sum()), 4),
        "selection_rule": "deterministic; see module docstring",
        "inputs": [
            "data/processed/nco_entries_vol2.parquet",
            "data/raw/plfs/plfs_2023-24_jul-jun/csv/perv1.csv",
        ],
    }
    (processed_dir() / "pilot_selection.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
