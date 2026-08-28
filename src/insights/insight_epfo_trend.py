"""Substack chart: EPFO net payroll additions trend, young (18-25) vs 29+.

National net additions per month (EPFO-era series, Apr 2020 - Jul 2025);
6-month rolling means bold, monthly values faint. PRELIMINARY framing lives
in the atlas; this chart is raw EPFO administrative data.
"""

from __future__ import annotations

from datetime import date

import matplotlib.pyplot as plt
import polars as pl

from atlas_common import outputs_dir, processed_dir
from insights._style import (SB_BLACK, SB_GOLD, SB_RED, add_source,
                             apply_style, head_sub)

OUT = outputs_dir() / "substack"
DATASET = "EPFO monthly payroll releases (net new subscribers by age band), Apr 2020 - Jul 2025"


def main() -> None:
    apply_style()
    e = pl.read_parquet(processed_dir() / "epfo_payroll.parquet")
    nat = e.filter(pl.col("industry").is_null() & pl.col("state").is_null()
                   & pl.col("gender").is_null() & (pl.col("measure") == "net_payroll"))

    def series(bands, name):
        return (nat.filter(pl.col("age_band").is_in(bands))
                .group_by("data_month").agg(pl.col("value").sum().alias(name))
                .sort("data_month"))

    j = (series(["18-21", "22-25"], "young")
         .join(series(["29-35", ">35"], "older"), on="data_month")
         .with_columns(pl.col("young").rolling_mean(6).alias("young6"),
                       pl.col("older").rolling_mean(6).alias("older6")))
    months = j["data_month"].to_list()
    x = list(range(len(months)))

    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    ax.axhline(0, color="#c9c7c0", lw=0.8)
    ax.plot(x, [v / 1e6 for v in j["young"]], color=SB_RED, lw=0.7, alpha=0.3)
    ax.plot(x, [v / 1e6 for v in j["older"]], color=SB_BLACK, lw=0.7, alpha=0.25)
    ax.plot(x, [v / 1e6 if v is not None else None for v in j["young6"]],
            color=SB_RED, lw=2.0, label="Age 18-25")
    ax.plot(x, [v / 1e6 if v is not None else None for v in j["older6"]],
            color=SB_BLACK, lw=2.0, label="Age 29+")
    chatgpt = months.index("2022-11")
    ax.axvline(chatgpt, color=SB_GOLD, lw=1.4, ls="--")
    ax.text(chatgpt + 0.8, 0.86, "ChatGPT\n(Nov 2022)", fontsize=8, color="#a67102")
    ticks = [i for i, m in enumerate(months) if m.endswith(("-04",)) and m[3] in "01234567"]
    ticks = [i for i, m in enumerate(months) if m.endswith("-04")]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"Apr {m[:4]}" for i, m in enumerate(months) if m.endswith("-04")],
                       fontsize=8)
    ax.set_ylabel("Net new EPFO subscribers (millions/month)")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    head_sub(ax, "Young payroll hiring flatlined - older hiring grew\n"
                 "Net EPFO additions per month (bold: 6-month rolling mean). Age 18-25\n"
                 "(red): 0.59M/month in the year before ChatGPT, 0.60M in the last twelve;\n"
                 "age 29+ (black): 0.42M to 0.51M over the same span.")
    add_source(fig, DATASET)
    fig.savefig(OUT / "insight_epfo_young_trend.png", bbox_inches="tight")
    plt.close(fig)

    prov = OUT / "provenance.md"
    existing = prov.read_text() if prov.exists() else "# Substack chart provenance\n\n"
    pre = j.filter((pl.col("data_month") >= "2021-11") & (pl.col("data_month") < "2022-11"))
    post = j.filter(pl.col("data_month") >= "2024-08")
    existing += (f"### insight_epfo_young_trend ({date.today()})\n"
                 f"young avg 2021-11..2022-10: {float(pre['young'].mean())/1e6:.3f}M; "
                 f"last 12m: {float(post['young'].mean())/1e6:.3f}M; "
                 f"older pre: {float(pre['older'].mean())/1e6:.3f}M; last 12m: "
                 f"{float(post['older'].mean())/1e6:.3f}M; 64 months Apr2020-Jul2025\n"
                 f"Source: {DATASET}.\n")
    prov.write_text(existing)
    print("trend chart written")


if __name__ == "__main__":
    main()
