"""Substack charts: most-impacted industries and job types, with absolute
workforce (millions) and wage-bill stakes. PRELIMINARY scoring per D6.

Outputs: outputs/substack/insight_{sector_exposure,jobtypes,wagebill_sectors}.png
"""

from __future__ import annotations

from datetime import date

import matplotlib.pyplot as plt
import polars as pl

from atlas_common import outputs_dir, processed_dir
from insights._style import (SB_GOLD, SB_GREY, SB_RED, add_source, apply_style,
                             head_sub)

OUT = outputs_dir() / "substack"
DATASET = "PLFS 2023-24 unit data x NCO-2015 task-exposure index (preliminary LLM scoring)"
PROV: list[str] = []

# NIC-2008 2-digit division -> friendly sector label
SECTIONS = [
    ("Agriculture", range(1, 4)), ("Mining", range(5, 10)),
    ("Manufacturing", range(10, 34)), ("Utilities", range(35, 40)),
    ("Construction", range(41, 44)), ("Trade & retail", range(45, 48)),
    ("Transport & logistics", range(49, 54)), ("Hotels & food", range(55, 57)),
    ("IT & communication", range(58, 64)), ("Finance & insurance", range(64, 67)),
    ("Real estate", range(68, 69)), ("Professional services", range(69, 76)),
    ("Admin & support svcs", range(77, 83)), ("Public administration", range(84, 85)),
    ("Education", range(85, 86)), ("Health & social work", range(86, 89)),
    ("Other services", range(90, 100)),
]

GROUP_NAMES = {
    "251": "Software developers", "241": "Finance professionals",
    "431": "Numerical clerks", "263": "Social/religious professionals",
    "243": "Sales & PR professionals", "235": "Other teaching professionals",
    "242": "Administration professionals", "264": "Authors & journalists",
    "411": "General office clerks", "331": "Financial associate professionals",
    "334": "Secretaries (admin)", "341": "Legal/social associates",
    "233": "Secondary teachers", "234": "Primary teachers",
    "522": "Shop salespersons", "351": "ICT technicians",
    "252": "Database professionals", "212": "Statisticians & actuaries", "216": "Architects & designers",
    "122": "Sales & marketing managers",
}


def _df() -> pl.DataFrame:
    df = (pl.read_parquet(processed_dir() / "plfs_exposure_PRELIMINARY.parquet")
          .filter(pl.col("beta").is_not_null()))
    div = pl.col("nic5").cast(pl.Utf8).str.zfill(5).str.slice(0, 2).cast(pl.Int32, strict=False)
    sect = pl.lit(None, dtype=pl.Utf8)
    for name, rng in SECTIONS[::-1]:
        sect = pl.when(div.is_in(list(rng))).then(pl.lit(name)).otherwise(sect)
    return df.with_columns(sect.alias("sector_name"))


def _save(fig, name: str, numbers: str) -> None:
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight")
    plt.close(fig)
    PROV.append(f"### {name} ({date.today()})\n{numbers}\nSource: {DATASET}.\n")


def chart_sectors(df: pl.DataFrame) -> None:
    nat = float((df["beta"] * df["weight"]).sum() / df["weight"].sum())
    g = (df.filter(pl.col("sector_name").is_not_null())
         .group_by("sector_name")
         .agg(((pl.col("beta") * pl.col("weight")).sum() / pl.col("weight").sum()).alias("E"),
              (pl.col("weight").sum() / 1e6).alias("workers_m"))
         .filter(pl.col("workers_m") > 2).sort("E"))
    names, E, wm = g["sector_name"].to_list(), g["E"].to_list(), g["workers_m"].to_list()
    fig, ax = plt.subplots(figsize=(7, 5.6))
    colors = [SB_RED if e > nat else SB_GREY for e in E]
    ypos = range(len(names))
    ax.barh(list(ypos), E, color=colors, height=0.62)
    ax.axvline(nat, color=SB_GOLD, lw=1.4, ls="--")
    ax.text(nat + 0.003, len(names) - 0.2, f"national avg {nat:.2f}", fontsize=8.5, color="#a67102")
    for y, e, w in zip(ypos, E, wm):
        ax.text(e + 0.004, y, f"{e:.2f}  ({w:,.0f}M workers)", va="center", fontsize=8,
                color=SB_RED if e > nat else SB_GREY, fontweight="bold")
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlim(0, max(E) * 1.55)
    head_sub(ax, "IT and finance are India's AI frontline - and its smallest sectors\n"
                 "Mean exposure score by industry (sectors over 2M workers); red: above\n"
                 "national average; labels show workers employed. PLFS 2023-24.")
    ax.set_xlabel("Mean exposure score (0-1)")
    add_source(fig, DATASET)
    _save(fig, "insight_sector_exposure",
          "; ".join(f"{n}: E={e:.3f}, {w:.1f}M" for n, e, w in zip(names, E, wm)))


def chart_jobtypes(df: pl.DataFrame) -> None:
    g = (df.group_by("group3")
         .agg(((pl.col("beta") * pl.col("weight")).sum() / pl.col("weight").sum()).alias("E"),
              (pl.col("weight").sum() / 1e6).alias("workers_m"))
         .filter(pl.col("workers_m") >= 0.3).sort("E", descending=True).head(10).sort("E"))
    names = [GROUP_NAMES.get(c, f"NCO {c}") for c in g["group3"].to_list()]
    E, wm = g["E"].to_list(), g["workers_m"].to_list()
    fig, ax = plt.subplots(figsize=(7, 5.2))
    ypos = range(len(names))
    ax.barh(list(ypos), E, color=SB_RED, height=0.62)
    for y, e, w in zip(ypos, E, wm):
        ax.text(e + 0.008, y, f"{e:.2f}  ({w:.1f}M)", va="center", fontsize=8.5,
                color=SB_RED, fontweight="bold")
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlim(0, max(E) * 1.3)
    total_m = sum(wm)
    head_sub(ax, f"The most exposed jobs employ {total_m:.0f} million Indians\n"
                 "Ten most exposed occupation groups with at least 0.3M workers;\n"
                 "labels: exposure score and workers employed (millions). PLFS 2023-24.")
    ax.set_xlabel("Mean exposure score (0-1)")
    add_source(fig, DATASET)
    _save(fig, "insight_jobtypes",
          "; ".join(f"{n}: E={e:.3f}, {w:.2f}M" for n, e, w in zip(names, E, wm)))


def chart_wagebill_sectors(df: pl.DataFrame) -> None:
    e = df.filter((pl.col("monthly_earnings") > 0) & pl.col("sector_name").is_not_null())
    g = (e.group_by("sector_name")
         .agg((pl.col("monthly_earnings") * pl.col("weight")).sum().alias("wb"),
              (pl.col("monthly_earnings") * pl.col("weight"))
              .filter(pl.col("beta") >= 0.5).sum().alias("wb_hi"),
              (pl.col("weight").filter(pl.col("beta") >= 0.5).sum() / 1e6).alias("hi_workers_m"))
         .with_columns((pl.col("wb_hi") / pl.col("wb") * 100).alias("pct"),
                       # Rs thousand crore per month: 1 kcr = 1e3 x 1e7 = 1e10 Rs
                       (pl.col("wb") / 1e10).alias("wb_kcr"))
         .filter(pl.col("wb_kcr") > 0.5).sort("pct").tail(10))
    names, pct = g["sector_name"].to_list(), g["pct"].to_list()
    him = g["hi_workers_m"].to_list()
    avg = float(e.filter(pl.col("beta") >= 0.5)
                .select(pl.col("monthly_earnings") * pl.col("weight")).sum().item()
                / e.select(pl.col("monthly_earnings") * pl.col("weight")).sum().item()) * 100
    fig, ax = plt.subplots(figsize=(7, 5.2))
    ypos = range(len(names))
    colors = [SB_RED if p > avg else SB_GREY for p in pct]
    ax.barh(list(ypos), pct, color=colors, height=0.62)
    ax.axvline(avg, color=SB_GOLD, lw=1.4, ls="--")
    ax.text(avg + 0.6, len(names) - 0.45, f"economy avg {avg:.0f}%", fontsize=8.5, color="#a67102")
    for y, p, w in zip(ypos, pct, him):
        lab = f"{p:.0f}%  ({w:.1f}M workers)" if w >= 0.05 else f"{p:.0f}%"
        ax.text(p + 0.5, y, lab, va="center", fontsize=8.5,
                color=colors[y], fontweight="bold")
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlim(0, max(pct) * 1.45)
    head_sub(ax, "In IT, three-quarters of the paycheque sits in exposed jobs\n"
                 "Share of each sector's wage bill paid to workers in high-exposure\n"
                 "occupations (score 0.5+); red: above economy average; labels add\n"
                 "exposed workers. Salaried + self-employed earnings, PLFS 2023-24.")
    ax.set_xlabel("% of sector's wage bill in high-exposure occupations")
    add_source(fig, DATASET)
    _save(fig, "insight_wagebill_sectors",
          "; ".join(f"{n}: {p:.1f}%, {w:.2f}M hi-workers" for n, p, w in zip(names, pct, him))
          + f"; economy avg {avg:.1f}%")


def main() -> None:
    apply_style()
    OUT.mkdir(parents=True, exist_ok=True)
    df = _df()
    chart_sectors(df)
    chart_jobtypes(df)
    chart_wagebill_sectors(df)
    chart_top_functions(df)
    prov = OUT / "provenance.md"
    existing = prov.read_text() if prov.exists() else "# Substack chart provenance\n\n"
    prov.write_text(existing + "\n".join(PROV))
    print("4 charts written")




def chart_top_functions(df: pl.DataFrame) -> None:
    """Top-10 by exposure score with NO employment floor - the league table
    from the results brief (statisticians & actuaries on top), with worker
    counts labelled so tiny elite functions read as tiny."""
    extra_names = {"264": "Authors, journalists & linguists", "412": "Secretaries",
                   "252": "Database & network professionals"}
    names_map = {**GROUP_NAMES, **extra_names}
    idx = pl.read_parquet(processed_dir() / "group3_index_PRELIMINARY.parquet")
    emp = (df.group_by("group3").agg((pl.col("weight").sum() / 1e6).alias("workers_m")))
    g = (idx.filter(pl.col("n_tasks") >= 5)
         .join(emp, on="group3", how="inner")
         .select("group3", pl.col("beta").alias("E"), "workers_m")
         .sort("E", descending=True).head(10).sort("E"))
    names = [names_map.get(c, f"NCO {c}") for c in g["group3"].to_list()]
    E, wm = g["E"].to_list(), g["workers_m"].to_list()

    def wlab(w):
        return f"{w:.1f}M" if w >= 0.95 else f"{w*1000:.0f}k"

    fig, ax = plt.subplots(figsize=(7, 5.2))
    ypos = range(len(names))
    ax.barh(list(ypos), E, color=SB_RED, height=0.62)
    for y, e, w in zip(ypos, E, wm):
        ax.text(e + 0.01, y, f"{e:.2f}  ({wlab(w)} workers)", va="center",
                fontsize=8.5, color=SB_RED, fontweight="bold")
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlim(0, 1.32)
    head_sub(ax, "Statisticians and actuaries top India's AI exposure league\n"
                 "Ten most exposed occupation groups, any size; labels: exposure score\n"
                 "and workers employed. Some frontline functions are tiny. PLFS 2023-24.")
    ax.set_xlabel("Mean exposure score (0-1)")
    add_source(fig, DATASET)
    _save(fig, "insight_top_functions",
          "; ".join(f"{n}: E={e:.3f}, {w:.3f}M" for n, e, w in zip(names, E, wm)))


if __name__ == "__main__":
    main()
