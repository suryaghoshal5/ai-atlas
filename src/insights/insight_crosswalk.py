"""Substack chart / Exhibit 4.7: native NCO exposure vs O*NET-crosswalked
exposure for the same 122 occupation groups (PRELIMINARY per D6).

Data: data/processed/crosswalk_comparison_PRELIMINARY.parquet
(built by analysis.crosswalk_compare).
"""

from __future__ import annotations

from datetime import date

import matplotlib.pyplot as plt
import polars as pl

from atlas_common import outputs_dir, processed_dir
from insights._style import SB_GREY, SB_RED, add_source, apply_style, head_sub

OUT = outputs_dir() / "substack"
DATASET = ("Eloundou et al. (2024) O*NET exposure scores via BLS/IBS SOC-ISCO crosswalk vs "
           "NCO-2015 native scores (preliminary LLM scoring); PLFS 2023-24 employment")

# label, (dx, dy), horizontal alignment
LABELS = {
    "251": ("Software developers", (0.02, -0.035), "left"),
    "413": ("Keyboard & data-entry clerks", (0.008, -0.048), "right"),
    "411": ("General office clerks", (-0.016, 0.002), "right"),
    "522": ("Shop salespersons (33M)", (-0.035, -0.012), "right"),
    "421": ("Tellers & cashiers", (-0.018, 0.008), "right"),
    "112": ("Managing directors", (0.025, -0.02), "left"),
    "212": ("Actuaries & statisticians", (-0.018, 0.006), "right"),
}


def main() -> None:
    apply_style()
    df = pl.read_parquet(processed_dir() / "crosswalk_comparison_PRELIMINARY.parquet")

    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    ax.plot([0, 1], [0, 1], color="#c9c7c0", lw=1.1, ls="--", zorder=1)
    ax.text(0.86, 0.895, "agreement", fontsize=8, color="#8a8781", rotation=45,
            ha="center", va="center")

    x = df["beta_crosswalked"].to_list()
    y = df["beta_native"].to_list()
    w = [max(v or 0, 0.05) for v in df["workers_m"].to_list()]
    sizes = [18 + 5.5 * v for v in w]
    hi = [g in LABELS for g in df["group3"].to_list()]
    ax.scatter([xi for xi, h in zip(x, hi) if not h], [yi for yi, h in zip(y, hi) if not h],
               s=[s for s, h in zip(sizes, hi) if not h], color=SB_GREY, alpha=0.45,
               linewidths=0, zorder=2)
    for g, xi, yi, s in zip(df["group3"].to_list(), x, y, sizes):
        if g in LABELS:
            ax.scatter([xi], [yi], s=s, color=SB_RED, alpha=0.9, linewidths=0, zorder=3)
            lab, (dx, dy), ha = LABELS[g]
            ax.text(xi + dx, yi + dy, lab, fontsize=8, color="#1a1a1a", ha=ha, zorder=4)

    ax.set_xlim(0, 0.92)
    ax.set_ylim(0, 0.98)
    ax.set_xlabel("Exposure via O*NET crosswalk (Eloundou et al. 2024 scores)")
    ax.set_ylabel("Exposure from India-native NCO-2015 task content")
    head_sub(ax, "Route India through O*NET and exposure more than doubles\n"
                 "Each dot: one NCO 3-digit occupation group (size = PLFS workers),\n"
                 "scored from its own Indian task content (y) vs the US O*NET scores\n"
                 "its crosswalk twin receives (x). Employment-weighted mean: 0.086\n"
                 "native vs 0.204 crosswalked. The two agree where work is globalised\n"
                 "(software); the crosswalk overstates paper-and-presence India.")
    add_source(fig, DATASET, y=-0.035)
    fig.savefig(OUT / "insight_crosswalk_divergence.png", bbox_inches="tight")
    plt.close(fig)

    prov = OUT / "provenance.md"
    existing = prov.read_text() if prov.exists() else "# Substack chart provenance\n\n"
    existing += (f"### insight_crosswalk_divergence ({date.today()})\n"
                 "122/122 groups matched via O*NET-SOC2019->2010->SOC10->ISCO-08 minor; "
                 "corr 0.78; emp-weighted native 0.086 vs crosswalked 0.204; mean |gap| 0.124 "
                 "(emp-weighted); 82/122 groups |gap|>=0.10 holding 191M workers (41%). "
                 "Key rows: 251 software 0.74/0.79; 413 keyboard clerks 0.27/0.82; "
                 "411 office clerks 0.30/0.60; 522 shop sales 0.17/0.41; 421 tellers 0.26/0.42; "
                 "112 managing directors 0.15/0.49; 212 actuaries 0.91/0.69.\n"
                 f"Source: {DATASET}.\n")
    prov.write_text(existing)
    print("crosswalk chart written")


if __name__ == "__main__":
    main()
