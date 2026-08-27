"""Substack chart: the five-cluster occupation typology on the exposure x
employment plane (k-means, silhouette-selected k=5). PRELIMINARY per D6.

Cluster colours validated (dataviz six-checks, light surface):
red / gold / blue / green / purple; grey is reserved for nothing here.
"""

from __future__ import annotations

from datetime import date

import matplotlib.pyplot as plt
import polars as pl

from atlas_common import outputs_dir, processed_dir
from insights._style import SB_GREY, add_source, apply_style, head_sub

OUT = outputs_dir() / "substack"
DATASET = "PLFS 2023-24 unit data x NCO-2015 task-exposure index (preliminary LLM scoring)"

# Colours are keyed by cluster NAME, never by k-means id: ids are arbitrary and
# permute whenever the features or the data move (see analysis.typology.name_clusters).
COLOURS = {
    "Frontier professionals": "#C8102E",   # alpha-led, graduate, urban
    "The paperwork layer":    "#eda100",   # E2-heavy clerical/records
    "Managers & teachers":    "#0072B2",   # authority/presence-bound middle
    "Rural agrarian mass":    "#3D8B37",   # insulated, rural
    "Urban manual & retail":  "#7C5CB0",   # insulated, urban
}


def main() -> None:
    apply_style()
    OUT.mkdir(parents=True, exist_ok=True)
    typ = pl.read_parquet(processed_dir() / "occupation_typology_PRELIMINARY.parquet")
    if "name" not in typ.columns:
        raise SystemExit("typology parquet predates named clusters — rerun `make typology`")
    idx = pl.read_parquet(processed_dir() / "group3_index_PRELIMINARY.parquet")
    g = typ.join(idx.select("group3", pl.col("beta").alias("E")), on="group3")

    present = set(g["name"].to_list())
    names = [n for n in COLOURS if n in present] + sorted(present - set(COLOURS))

    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    for name in names:
        s = g.filter(pl.col("name") == name)
        ax.scatter(s["E"], s["workers_m"], s=[max(14, w * 26) for w in s["workers_m"]],
                   c=COLOURS.get(name, SB_GREY), alpha=0.6, edgecolors="white", linewidths=0.6,
                   label=f"{name} ({float(s['workers_m'].sum()):.0f}M)")
    ax.set_yscale("log")
    ax.set_ylim(0.01, 400)
    ax.set_xlim(0, 1.0)
    anns = [("611", "Crop farmers", (0.02, -12)), ("931", "Manual helpers", (0.02, 6)),
            ("522", "Shop sales", (0.02, 6)), ("112", "Proprietors", (0.018, 2.5)),
            ("234", "Primary teachers", (0.02, 1.6)), ("411", "Office clerks", (0.018, -0.9)),
            ("431", "Numerical clerks", (0.018, -0.35)), ("251", "Software devs", (0.02, 0.6)),
            ("241", "Finance profs", (0.018, -0.55)), ("212", "Actuaries", (-0.02, 0.004))]
    for code, lab, (dx, dy) in anns:
        r = g.filter(pl.col("group3") == code)
        if r.height:
            row = r.row(0, named=True)
            ax.annotate(lab, (row["E"], row["workers_m"]),
                        xytext=(row["E"] + dx, row["workers_m"] + dy),
                        fontsize=7.3, color="#52514e", ha="right" if dx < 0 else "left")
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker="o", linestyle="", markersize=7,
                      markerfacecolor=COLOURS.get(name, SB_GREY), markeredgecolor="white",
                      alpha=0.85,
                      label=f"{name} ({float(g.filter(pl.col('name') == name)['workers_m'].sum()):.0f}M)")
               for name in names]
    ax.legend(handles=handles, frameon=False, fontsize=7.8, loc="lower left",
              borderpad=0.6, labelspacing=0.9,
              title="five clusters (k-means on 7 features)", title_fontsize=7.6)
    head_sub(ax, "India's workforce sorts into five AI worlds\n"
                 "122 occupation groups clustered on exposure mix, education, earnings,\n"
                 "gender, age and location (k-means, k chosen by silhouette). Point size =\n"
                 "workers; legend totals = cluster employment. PLFS 2023-24.")
    ax.set_xlabel("Mean exposure score (0-1)")
    ax.set_ylabel("Workers employed (millions, log scale)")
    add_source(fig, DATASET)
    fig.savefig(OUT / "insight_typology.png", bbox_inches="tight")
    plt.close(fig)

    prov = OUT / "provenance.md"
    existing = prov.read_text() if prov.exists() else "# Substack chart provenance\n\n"
    prof = pl.read_csv(outputs_dir() / "tables" / "typology_profiles_PRELIMINARY.csv")
    existing += (f"### insight_typology ({date.today()})\n"
                 f"k={prof.height}; profiles: {prof.to_dicts()}\nSource: {DATASET}.\n")
    prov.write_text(existing)
    print("typology chart written")


if __name__ == "__main__":
    main()
