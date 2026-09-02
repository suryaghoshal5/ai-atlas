"""Substack charts: EPFO net payroll additions by age band (national series,
Apr 2020 - Jul 2025). Raw EPFO administrative data.

Two views:
  insight_epfo_young_trend.png    levels, 6-mo rolling means, all six bands
  insight_epfo_trend_indexed.png  same series indexed to pre-ChatGPT avg = 100
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

# Exits reach EPFO with a claim-filing lag, so the freshest months understate
# ceased members and overstate net additions (documented in data/raw/epfo/NOTES.md).
# Rolling means touching those months are drawn dashed as provisional.
PROVISIONAL_FROM = "2025-03"
BASE_LO, BASE_HI = "2022-01", "2022-10"  # pre-ChatGPT base window for the index


def load_series() -> tuple[list[str], dict[str, list[float | None]]]:
    e = pl.read_parquet(processed_dir() / "epfo_payroll.parquet")
    nat = e.filter(pl.col("industry").is_null() & pl.col("state").is_null()
                   & pl.col("gender").is_null() & (pl.col("measure") == "net_payroll"))
    months = sorted(m for m in nat["data_month"].unique().to_list() if m >= "2020-04")
    series = {}
    for band, _, _ in BANDS:
        s = (nat.filter(pl.col("age_band") == band).sort("data_month")
             .filter(pl.col("data_month") >= "2020-04")
             .with_columns(pl.col("value").rolling_mean(6).alias("r6")))
        series[band] = [v / 1e6 if v is not None else None for v in s["r6"]]
    return months, series


def _frame(ax, months: list[str], n: int) -> int:
    chatgpt = months.index("2022-11")
    ax.axvline(chatgpt, color="#b9b7b0", lw=1.2, ls="--")
    ticks = [i for i, m in enumerate(months) if m.endswith("-04")]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"Apr {m[:4]}" for m in months if m.endswith("-04")], fontsize=8)
    ax.set_xlim(0, n + 5)
    return chatgpt


def _end_labels(ax, ends: list[tuple[float, str, str]], x_at: float, gap: float) -> None:
    ends.sort(key=lambda t: t[0])
    prev = None
    for val, lab, color in ends:
        y = val if prev is None or val - prev >= gap else prev + gap
        ax.text(x_at, y, lab, fontsize=8.2, color=color, fontweight="bold", va="center")
        prev = y


def chart_levels(months: list[str], series: dict) -> list[str]:
    x = list(range(len(months)))
    cut = months.index(PROVISIONAL_FROM)
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    ax.axhline(0, color="#c9c7c0", lw=0.8)
    prov_bits, ends = [], []
    for band, color, lab in BANDS:
        vals = series[band]
        ax.plot(x[: cut + 1], vals[: cut + 1], color=color, lw=1.9)
        ax.plot(x[cut:], vals[cut:], color=color, lw=1.6, ls=(0, (2, 2)), alpha=0.55)
        last = next(v for v in reversed(vals) if v is not None)
        ends.append((last, lab, color))
        prov_bits.append(f"{band}: last r6={last:.3f}M")
    ax.set_ylim(-0.03, 0.41)
    _end_labels(ax, ends, len(x) - 0.4, 0.02)
    chatgpt = _frame(ax, months, len(x))
    ax.text(chatgpt + 0.8, 0.405, "ChatGPT\n(Nov 2022)", fontsize=8,
            color="#898781", va="top")
    ax.set_ylabel("Net new EPFO subscribers (millions/month, 6-mo rolling mean)")
    head_sub(ax, "India's formal payroll runs on the under-25s\n"
                 "Net EPFO additions by age band, 6-month rolling means. Reds: the young\n"
                 "entry bands (18-25); gold: 26-28; black/grey: 29+ and under-18.\n"
                 "Dashed tail: provisional — EPFO records exits with a lag, so recent\n"
                 "net additions are overstated. Apr 2020 - Jul 2025.")
    add_source(fig, DATASET)
    fig.savefig(OUT / "insight_epfo_young_trend.png", bbox_inches="tight")
    plt.close(fig)
    return prov_bits


def chart_indexed(months: list[str], series: dict) -> list[str]:
    """Each band's rolling mean rebased so its Jan-Oct 2022 average = 100.

    Under-18 is dropped: its base is ~7k/month (vs 150-300k for the working
    bands), so an index on it is noise.
    """
    x = list(range(len(months)))
    cut = months.index(PROVISIONAL_FROM)
    lo, hi = months.index(BASE_LO), months.index(BASE_HI)
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    ax.axhline(100, color="#c9c7c0", lw=1.0)
    ax.text(1, 101.5, "pre-ChatGPT average = 100", fontsize=7.6, color="#8a8781")
    prov_bits, ends = [], []
    for band, color, lab in BANDS:
        if band == "<18":
            continue
        vals = series[band]
        base_vals = [v for v in vals[lo: hi + 1] if v is not None]
        base = sum(base_vals) / len(base_vals)
        idx = [100 * v / base if v is not None else None for v in vals]
        ax.plot(x[: cut + 1], idx[: cut + 1], color=color, lw=1.9)
        ax.plot(x[cut:], idx[cut:], color=color, lw=1.6, ls=(0, (2, 2)), alpha=0.55)
        last_solid = next(v for v in reversed(idx[: cut + 1]) if v is not None)
        ends.append((last_solid, lab, color))
        prov_bits.append(f"{band}: base={base:.3f}M, Feb-2025 idx={last_solid:.0f}")
    ymax = 145
    ax.set_ylim(0, ymax)
    _end_labels(ax, ends, len(x) - 0.4, 5.5)
    chatgpt = _frame(ax, months, len(x))
    ax.text(chatgpt + 0.8, ymax - 2, "ChatGPT\n(Nov 2022)", fontsize=8,
            color="#898781", va="top")
    ax.set_ylabel("Net additions, 6-mo rolling mean\n(index: Jan-Oct 2022 average = 100)")
    head_sub(ax, "The 22-25s never got back to their pre-ChatGPT pace\n"
                 "Net EPFO additions by age band, rebased to each band's own Jan-Oct\n"
                 "2022 average. Post-ChatGPT averages: 22-25 at 90, 18-21 at 99 —\n"
                 "vs 29-35 at 103 and 35+ at 105. Descriptive, not causal. End labels\n"
                 "at Feb 2025 (last mature month); dashed tail provisional (exit lag).")
    add_source(fig, DATASET)
    fig.savefig(OUT / "insight_epfo_trend_indexed.png", bbox_inches="tight")
    plt.close(fig)
    return prov_bits


def main() -> None:
    apply_style()
    months, series = load_series()
    prov_levels = chart_levels(months, series)
    prov_idx = chart_indexed(months, series)

    prov = OUT / "provenance.md"
    existing = prov.read_text() if prov.exists() else "# Substack chart provenance\n\n"
    existing += (f"### insight_epfo_young_trend ({date.today()})\n"
                 "6-mo rolling means, all bands; " + "; ".join(prov_levels)
                 + f"\nDashed from {PROVISIONAL_FROM}: provisional (exit-recording lag "
                 "overstates recent net additions; see data/raw/epfo/NOTES.md).\n"
                 f"Source: {DATASET}.\n")
    existing += (f"### insight_epfo_trend_indexed ({date.today()})\n"
                 f"Same series indexed to {BASE_LO}..{BASE_HI} avg = 100; under-18 "
                 "dropped (tiny base); " + "; ".join(prov_idx)
                 + f"\nDashed from {PROVISIONAL_FROM} as above.\nSource: {DATASET}.\n")
    prov.write_text(existing)
    print("trend charts written")


if __name__ == "__main__":
    main()
