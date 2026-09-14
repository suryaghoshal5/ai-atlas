"""Atlas grid: 463 squares, one million workers each, three sector bands,
each square an NCO-2015 3-digit group coloured by its exposure score, with a
drill-down group -> occupation -> task (E0 / E1 / E2). Presentation layer
only (like the rest of src/insights/): no paper number depends on it.

Outputs (outputs/atlas_grid/):
    atlas_grid_data.json   the hierarchy + square allocation the page renders
    index.html             self-contained page (template + embedded JSON)

Two build modes:
    default    reads the processed pipeline files (PLFS exposure merge, task
               statements, task scores) and writes the group3 x NIC-division
               headcount aggregate to outputs/atlas_grid/; if the PLFS merge is
               absent but that aggregate is present, builds from the aggregate.
               Status stamp = PRELIMINARY per D6.
    --fixture  reads ONLY files committed to the repo (task scores, pilot
               sheet, title table). Employment by group x sector is NOT
               available in the repo, so the fixture allocates squares with a
               deterministic synthetic split (seed 42) and stamps the page
               DEV_FIXTURE. Real task scores, real code hierarchy, fake
               headcounts: for exercising the renderer, never for reading
               results.

Square allocation is Hamilton / largest-remainder, sectors first then groups
within a sector, so the bands always sum to the national square count and each
band to its own rounded headcount. Groups that round to zero squares in a
sector are listed under that band as "below one square".
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import yaml

from atlas_common import REPO_ROOT, outputs_dir, processed_dir, run_seed

OUT = outputs_dir() / "atlas_grid"
TEMPLATE = Path(__file__).with_name("atlas_grid_template.html")
TITLES = REPO_ROOT / "config" / "nco2015_titles.yaml"
SCORES = REPO_ROOT / "outputs" / "full_batch_scoring" / "task_scores_full_PRELIMINARY.parquet"
PILOT_SHEET = REPO_ROOT / "outputs" / "pilot" / "pilot_scoring_sheet.csv"
VINTAGE = REPO_ROOT / "outputs" / "tables" / "vintage_check_PRELIMINARY.csv"
PROVENANCE = REPO_ROOT / "outputs" / "substack" / "provenance.md"

SQUARE_M = 1.0  # one square = one million workers

# NIC-2008 2-digit division -> three-sector split (Agriculture / Industry /
# Services). "Industry" is the secondary sector: manufacturing plus
# construction, mining and utilities. Change here to re-cut the bands.
SECTORS = [
    {"key": "agriculture", "label": "Agriculture",
     "sub": "crops, livestock, forestry, fishing (NIC 01-03)", "divs": range(1, 4)},
    {"key": "industry", "label": "Industry",
     "sub": "manufacturing, construction, mining, utilities (NIC 05-43)", "divs": range(5, 44)},
    {"key": "services", "label": "Services",
     "sub": "trade, transport, IT, finance, education, health, public administration (NIC 45-99)",
     "divs": range(45, 100)},
]

# Fixture-only sector totals (millions), from outputs/substack/provenance.md
# (insight_sector_exposure, 2026-08-27), scaled to a 463-square canvas.
FIXTURE_SECTOR_M = {"agriculture": 193.9, "industry": 54.0 + 59.9 + 2.8, "services": 149.9}


# ---------------------------------------------------------------- allocation
def largest_remainder(weights: list[float], total: int) -> list[int]:
    """Hamilton apportionment: integer shares of `total` proportional to weights."""
    s = sum(weights)
    if total <= 0 or s <= 0:
        return [0] * len(weights)
    quotas = [w / s * total for w in weights]
    floors = [math.floor(q) for q in quotas]
    short = total - sum(floors)
    order = sorted(range(len(weights)), key=lambda i: (quotas[i] - floors[i], weights[i]), reverse=True)
    for i in order[:short]:
        floors[i] += 1
    return floors


def sector_of(div: int | None) -> str | None:
    if div is None:
        return None
    for s in SECTORS:
        if div in s["divs"]:
            return s["key"]
    return None


# ------------------------------------------------------------------ hierarchy
def build_hierarchy(scores: pl.DataFrame, tasks: pl.DataFrame, titles: dict) -> dict:
    """group3 -> families -> occupations -> tasks, with alpha/beta/zeta at every
    level (tasks weighted equally, per src/index/build.py)."""
    df = (scores.filter(pl.col("score").is_in(["E0", "E1", "E2"]))
          .join(tasks.select("task_id", "task_text", "occupation_title"), on="task_id", how="left")
          .with_columns(pl.col("nco_code").str.slice(0, 4).alias("family"))
          .sort("task_id"))

    def stats(part: pl.DataFrame) -> dict:
        n = part.height
        e = {k: int((part["score"] == k).sum()) for k in ("E0", "E1", "E2")}
        return {"n_tasks": n, "e": [e["E0"], e["E1"], e["E2"]],
                "alpha": round(e["E1"] / n, 4) if n else None,
                "beta": round((e["E1"] + 0.5 * e["E2"]) / n, 4) if n else None,
                "zeta": round((e["E1"] + e["E2"]) / n, 4) if n else None}

    groups: dict[str, dict] = {}
    for (g,), gdf in df.group_by("group3", maintain_order=True):
        fams = []
        for (f,), fdf in gdf.group_by("family", maintain_order=True):
            occs = []
            for (code,), odf in fdf.group_by("nco_code", maintain_order=True):
                title = odf["occupation_title"].drop_nulls()
                occs.append({
                    "code": code,
                    "title": title[0] if title.len() else f"NCO {code}",
                    **stats(odf),
                    "tasks": [{"id": r["task_id"], "s": r["score"],
                               "t": r["task_text"] or ""} for r in odf.iter_rows(named=True)],
                })
            fams.append({"code": f, "title": titles["families"].get(f, f"NCO family {f}"),
                         **stats(fdf), "occupations": occs})
        groups[g] = {"code": g, "title": titles["groups"].get(g, f"NCO group {g}"),
                     **stats(gdf), "families": fams}
    return groups


# ------------------------------------------------------------------ assembly
def assemble(groups: dict, emp: dict[str, dict[str, float]], status: str, notes: list[str],
             wbeta: dict[str, float] | None = None) -> dict:
    """emp: group3 -> {sector_key: workers_m}. wbeta: optional worker-weighted
    beta per group (from the PLFS merge); falls back to the task-level beta."""
    for g in groups.values():
        g["by_sector"] = {s["key"]: round(emp.get(g["code"], {}).get(s["key"], 0.0), 3) for s in SECTORS}
        g["workers_m"] = round(sum(g["by_sector"].values()), 3)

    total_m = sum(g["workers_m"] for g in groups.values())
    n_sq = int(round(total_m / SQUARE_M))
    sector_m = [sum(g["by_sector"][s["key"]] for g in groups.values()) for s in SECTORS]
    sector_sq = largest_remainder(sector_m, n_sq)

    def wmean(keys: list[str], sector: str | None) -> float | None:
        num = den = 0.0
        for k in keys:
            g = groups[k]
            w = g["by_sector"][sector] if sector else g["workers_m"]
            b = g["beta"]
            if b is None or w <= 0:
                continue
            num += w * b
            den += w
        return round(num / den, 4) if den else None

    sectors_out = []
    for s, m, sq in zip(SECTORS, sector_m, sector_sq):
        members = [g for g in groups.values() if g["by_sector"][s["key"]] > 0]
        members.sort(key=lambda g: (-(g["beta"] or 0), g["code"]))
        counts = largest_remainder([g["by_sector"][s["key"]] for g in members], sq)
        cells = [{"g": g["code"], "n": n} for g, n in zip(members, counts) if n > 0]
        small = [{"g": g["code"], "w": g["by_sector"][s["key"]]}
                 for g, n in zip(members, counts) if n == 0]
        sectors_out.append({"key": s["key"], "label": s["label"], "sub": s["sub"],
                            "workers_m": round(m, 2), "squares": sq,
                            "beta": wmean([g["code"] for g in members], s["key"]),
                            "n_groups": len(cells), "cells": cells, "small": small})

    e_tot = [sum(g["e"][i] for g in groups.values()) for i in range(3)]
    return {
        "status": status,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "square_m": SQUARE_M,
        "total_squares": n_sq,
        "notes": notes,
        "national": {"workers_m": round(total_m, 2), "n_groups": len(groups),
                     "beta": wmean(list(groups), None), "tasks_e": e_tot,
                     "n_tasks": sum(e_tot)},
        "sectors": sectors_out,
        "groups": groups,
    }


# --------------------------------------------------------------------- inputs
def load_titles() -> dict:
    t = yaml.safe_load(TITLES.read_text())
    return {"groups": {str(k): v for k, v in t["groups"].items()},
            "families": {str(k): v for k, v in t["families"].items()}}


EMP_AGG = OUT / "group_by_nic_division_PRELIMINARY.csv"


def aggregate_plfs() -> pl.DataFrame:
    """PLFS worker records -> headcount (millions) by NCO group3 x NIC-2008
    2-digit division. 122 x ~88 rows, no individual-level data: safe to move or
    commit, and enough to rebuild the grid anywhere."""
    plfs = pl.read_parquet(processed_dir() / "plfs_exposure_PRELIMINARY.parquet")
    div = pl.col("nic5").cast(pl.Utf8).str.zfill(5).str.slice(0, 2).cast(pl.Int32, strict=False)
    return (plfs.with_columns(div.alias("nic_div"))
            .group_by("group3", "nic_div")
            .agg((pl.col("weight").sum() / 1e6).alias("workers_m"))
            .sort("group3", "nic_div"))


def load_real() -> tuple[pl.DataFrame, pl.DataFrame, dict, list[str]]:
    scores = pl.read_parquet(SCORES)
    tasks = pl.read_parquet(processed_dir() / "task_statements_full.parquet")
    if (processed_dir() / "plfs_exposure_PRELIMINARY.parquet").exists():
        agg = aggregate_plfs()
        OUT.mkdir(parents=True, exist_ok=True)
        agg.write_csv(EMP_AGG)
        emp_src = "PLFS merge (aggregate written to outputs/atlas_grid/)"
    elif EMP_AGG.exists():
        agg = pl.read_csv(EMP_AGG, schema_overrides={"group3": pl.Utf8, "nic_div": pl.Int32})
        emp_src = f"{EMP_AGG.relative_to(REPO_ROOT)} (pre-aggregated from the PLFS merge)"
    else:
        raise SystemExit("Need data/processed/plfs_exposure_PRELIMINARY.parquet or "
                         f"{EMP_AGG.relative_to(REPO_ROOT)}; or run with --fixture.")
    emp: dict[str, dict[str, float]] = {}
    unsect = 0.0
    scored_groups = set(scores["group3"].unique().to_list())
    unindexed = {g: 0.0 for g in agg["group3"].unique().to_list() if g not in scored_groups}
    for r in agg.iter_rows(named=True):
        if r["group3"] in unindexed:
            unindexed[r["group3"]] += r["workers_m"]
            continue
        s = sector_of(r["nic_div"])
        if s is None:
            unsect += r["workers_m"]
            continue
        emp.setdefault(r["group3"], {}).setdefault(s, 0.0)
        emp[r["group3"]][s] += r["workers_m"]
    notes = [
        "PRELIMINARY per D6: LLM-only task scores, human-validation gate not cleared.",
        "Headcount: PLFS 2023-24, principal usual status employed, official weights "
        f"(mult/no_qtr), by NCO-2015 3-digit group x NIC-2008 division; source: {emp_src}.",
        f"Excluded from the bands: {sum(unindexed.values()):.2f}M workers in NCO groups with no "
        f"scored tasks ({', '.join(sorted(unindexed)) or 'none'}) and {unsect:.2f}M with no NIC division.",
        "Colour: beta = share E1 + 0.5 x share E2 of the group's NCO Vol II task statements.",
    ]
    return scores, tasks, emp, notes


def load_fixture() -> tuple[pl.DataFrame, pl.DataFrame, dict, list[str]]:
    scores = pl.read_parquet(SCORES)
    full = processed_dir() / "task_statements_full.parquet"
    if full.exists():
        # the parsed NCO Vol II statements are present (not committed, but may be
        # dropped in): full titles and task text, only the headcounts stay synthetic
        tasks = pl.read_parquet(full).select("task_id", "task_text", "occupation_title")
        text_note = ("Occupation titles and task text: NCO-2015 Vol II statements "
                     "(data/processed/task_statements_full.parquet), complete.")
    else:
        pilot = pl.read_csv(PILOT_SHEET).select("task_id", "task_text", "occupation_title")
        vint = (pl.read_csv(VINTAGE, schema_overrides={"nco_code": pl.Utf8})
                .select(pl.col("nco_code").alias("code"), pl.col("title").alias("vtitle")).unique("code"))
        tasks = (scores.select("task_id", "nco_code")
                 .join(pilot, on="task_id", how="left")
                 .join(vint, left_on="nco_code", right_on="code", how="left")
                 .with_columns(pl.coalesce("occupation_title", "vtitle").alias("occupation_title"))
                 .select("task_id", "task_text", "occupation_title"))
        text_note = ("Occupation titles and task text are present only for the 50-occupation "
                     "pilot and the vintage-check occupations; everything else shows its NCO code.")

    rng = random.Random(run_seed())
    codes = sorted(scores["group3"].unique().to_list())
    raw: dict[str, dict[str, float]] = {}
    for g in codes:
        size = rng.lognormvariate(0, 1.2)
        d = g[0]
        if d == "6":
            mix = {"agriculture": 0.9, "industry": 0.02, "services": 0.08}
        elif d in "78":
            mix = {"agriculture": 0.03, "industry": 0.72, "services": 0.25}
        elif d == "9":
            mix = {"agriculture": 0.45, "industry": 0.3, "services": 0.25}
        else:
            mix = {"agriculture": 0.03, "industry": 0.12, "services": 0.85}
        raw[g] = {k: size * v * rng.uniform(0.7, 1.3) for k, v in mix.items()}
    target_total = 463 * SQUARE_M
    scale = target_total / sum(FIXTURE_SECTOR_M.values())
    emp: dict[str, dict[str, float]] = {g: {} for g in codes}
    for s, m in FIXTURE_SECTOR_M.items():
        col = sum(raw[g][s] for g in codes)
        for g in codes:
            emp[g][s] = raw[g][s] / col * m * scale
    notes = [
        "DEV FIXTURE: headcounts per occupation group are SYNTHETIC (seeded random split "
        "of provenance sector totals). Only the task scores, the codes and the exposure "
        "colours are real. Run `make atlas-grid` on a machine with the processed PLFS "
        "merge to replace them.",
        text_note,
        "Colour: beta = share E1 + 0.5 x share E2 of the group's NCO Vol II task statements "
        "(real, PRELIMINARY per D6).",
    ]
    return scores, tasks, emp, notes


# ----------------------------------------------------------------------- main
def render(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return TEMPLATE.read_text().replace("/*__ATLAS_DATA__*/", payload)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--fixture", action="store_true", help="build from committed files only")
    args = ap.parse_args(argv)

    titles = load_titles()
    if args.fixture:
        scores, tasks, emp, notes = load_fixture()
        status = "DEV_FIXTURE"
    else:
        scores, tasks, emp, notes = load_real()
        status = "PRELIMINARY"

    groups = build_hierarchy(scores, tasks, titles)
    data = assemble(groups, emp, status, notes)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "atlas_grid_data.json").write_text(json.dumps(data, ensure_ascii=False, indent=None))
    (OUT / "index.html").write_text(render(data))
    meta = {k: data[k] for k in ("status", "built_at", "total_squares")}
    meta["sectors"] = {s["key"]: {"workers_m": s["workers_m"], "squares": s["squares"]}
                       for s in data["sectors"]}
    meta["national"] = data["national"]
    (OUT / "atlas_grid.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
