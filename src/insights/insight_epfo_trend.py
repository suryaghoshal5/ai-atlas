"""Substack chart: EPFO net payroll additions, 6-month rolling means for ALL
age bands (national series, Apr 2020 - Jul 2025). Raw EPFO administrative data.
"""

from __future__ import annotations

from datetime import date

import matplotlib.pyplot as plt
import polars as pl

from atlas_common import outputs_dir, processed_dir
from insights._style import SB_BLACK, SB_GOLD, SB_RED, add_source, apply_style, head_sub

OUT = outputs_dir() / "substack"
DATASET = "EPFO monthly payroll releases (net new subscribers by age band), Apr 2020 - Jul 2025"

BANDS = [("18-21", SB_RED, "18-21"), ("22-25", "#e0636e", "22-25"),
         ("26-28", SB_GOLD, "26-28"), ("29-35", SB_BLACK, "29-35"),
         (">35", "#8a8781", "35+"), ("<18", "#c9c7c0", "under 18")]


def main() -> None:
    apply_style()
    e = pl.read_parquet(processed_dir() / "epfo_payroll.parquet")
    nat = e.filter(pl.col("industry").is_null() & pl.col("state").is_null()
                   & pl.col("gender").is_null() & (pl.col("measure") == "net_payroll"))
    months = sorted(nat["data_month"].unique().to_list())
    months = [m for m in months if m >= "2020-04"]
    x = list(range(len(months)))

    # Exits reach EPFO with a claim-filing lag, so the freshest months understate
    # ceased members and overstate net additions (documented in data/raw/epfo/NOTES.md).
    # Rolling means touching those months are drawn dashed as provisional.
    PROVISIONAL_FROM = "2025-03"
    cut = months.index(PROVISIONAL_FROM)

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    ax.axhline(0, color="#c9c7c0", lw=0.8)
    prov_bits = []
    ends = []
    for band, color, lab in BANDS:
        s = (nat.filter(pl.col("age_band") == band).sort("data_month")
             .filter(pl.col("data_month") >= "2020-04")
             .with_columns(pl.col("value").rolling_mean(6).alias("r6")))
        vals = [v / 1e6 if v is not None else None for v in s["r6"]]
        ax.plot(x[: cut + 1], vals[: cut + 1], color=color, lw=1.9)
        ax.plot(x[cut:], vals[cut:], color=color, lw=1.6, ls=(0, (2, 2)), alpha=0.55)
        last = next(v for v in reversed(vals) if v is not None)
        ends.append((last, lab, color))
        prov_bits.append(f"{band}: last r6={last:.3f}M")
    ax.set_ylim(-0.03, 0.41)
    # direct labels at right edge, nudged apart if stacked
    ends.sort(key=lambda t: t[0])
    prev = None
    for val, lab, color in ends:
        y = val
        if prev is not None and y - prev < 0.02:
            y = prev + 0.02
        ax.text(len(x) - 0.4, y, lab, fontsize=8.2, color=color,
                fontweight="bold", va="center")
        prev = y
    chatgpt = months.index("2022-11")
    ax.axvline(chatgpt, color="#b9b7b0", lw=1.2, ls="--")
    ax.text(chatgpt + 0.8, 0.405, "ChatGPT\n(Nov 2022)", fontsize=8,
            color="#898781", va="top")
    ticks = [i for i, m in enumerate(months) if m.endswith("-04")]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"Apr {m[:4]}" for m in months if m.endswith("-04")], fontsize=8)
    ax.set_xlim(0, len(x) + 5)
    ax.set_ylabel("Net new EPFO subscribers (millions/month, 6-mo rolling mean)")
    head_sub(ax, "The 22-25s carry India's payroll growth\n"
                 "Net EPFO additions by age band, 6-month rolling means. Reds: the young\n"
                 "entry bands (18-25); gold: 26-28; black/grey: 29+ and under-18.\n"
                 "Dashed tail: provisional — EPFO records exits with a lag, so recent\n"
                 "net additions are overstated. Apr 2020 - Jul 2025.")
    add_source(fig, DATASET)
    fig.savefig(OUT / "insight_epfo_young_trend.png", bbox_inches="tight")
    plt.close(fig)

    prov = OUT / "provenance.md"
    existing = prov.read_text() if prov.exists() else "# Substack chart provenance\n\n"
    existing += (f"### insight_epfo_young_trend ({date.today()})\n"
                 "6-mo rolling means, all bands; " + "; ".join(prov_bits)
                 + f"\nDashed from {PROVISIONAL_FROM}: provisional (exit-recording lag "
                 "overstates recent net additions; see data/raw/epfo/NOTES.md).\n"
                 f"Source: {DATASET}.\n")
    prov.write_text(existing)
    print("trend chart written")


if __name__ == "__main__":
    main()
