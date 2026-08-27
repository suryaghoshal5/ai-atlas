"""Design 2: entry-level ("canaries") analysis (ANALYSIS_PLAN §5).

Exhibit 6.1 — the section opener (Surya, Aug 24 2026): the entry-rung exposure
gradient. Static PLFS evidence that young white-collar workers are concentrated
in high-exposure occupations — the structural premise the EPFO event study then
tests dynamically. EPFO components remain to be built.

Outputs (PRELIMINARY until validation clears, per D6):
    outputs/figures/fig6_1_entry_rung_PRELIMINARY.{png,pdf}
    outputs/tables/tab6_1_entry_rung_PRELIMINARY.csv
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import polars as pl

from atlas_common import outputs_dir, processed_dir

AGE_BANDS = [(15, 19), (20, 24), (25, 29), (30, 34), (35, 39), (40, 44),
             (45, 49), (50, 54), (55, 59), (60, 64)]
WC_DIVS = ["1", "2", "3", "4"]

# paper figure style — plain matplotlib, no seaborn (CLAUDE.md tech stack)
STYLE = {
    "font.family": "serif",
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "figure.dpi": 200,
}


def entry_rung_table() -> pl.DataFrame:
    df = (
        pl.read_parquet(processed_dir() / "plfs_exposure_PRELIMINARY.parquet")
        .filter(pl.col("beta").is_not_null())
        .with_columns(pl.col("group3").str.slice(0, 1).alias("div"))
    )
    rows = []
    for lo, hi in AGE_BANDS:
        for seg, frame in [("white_collar", df.filter(pl.col("div").is_in(WC_DIVS))),
                           ("all_workers", df)]:
            s = frame.filter((pl.col("age") >= lo) & (pl.col("age") <= hi))
            w = float(s["weight"].sum())
            if w == 0:
                continue
            rows.append({
                "age_band": f"{lo}-{hi}",
                "segment": seg,
                "mean_beta": float((s["beta"] * s["weight"]).sum() / w),
                "share_hi_exposure": float(s.filter(pl.col("beta") >= 0.5)["weight"].sum() / w),
                "emp_weight_share": w,
            })
    return pl.DataFrame(rows)


def main() -> None:
    tab = entry_rung_table()
    tables_dir = outputs_dir() / "tables"
    figures_dir = outputs_dir() / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    tab.write_csv(tables_dir / "tab6_1_entry_rung_PRELIMINARY.csv")

    wc = tab.filter(pl.col("segment") == "white_collar")
    allw = tab.filter(pl.col("segment") == "all_workers")
    x = list(range(len(AGE_BANDS)))
    labels = [f"{lo}–{hi}" for lo, hi in AGE_BANDS]

    plt.rcParams.update(STYLE)
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9))

    ax = axes[0]
    ax.plot(x, wc["mean_beta"], marker="o", ms=3.5, lw=1.4, color="#1f3b6e",
            label="White-collar (NCO 1–4)")
    ax.plot(x, allw["mean_beta"], marker="s", ms=3, lw=1.1, color="#8a8f98",
            label="All workers")
    ax.set_ylabel("Mean exposure $\\beta$")
    ax.set_ylim(0, None)
    ax.legend(frameon=False, fontsize=7.5, loc="upper right")
    ax.set_title("(a) Exposure by age", fontsize=9)

    ax = axes[1]
    ax.plot(x, [v * 100 for v in wc["share_hi_exposure"]], marker="o", ms=3.5,
            lw=1.4, color="#1f3b6e", label="White-collar (NCO 1–4)")
    ax.plot(x, [v * 100 for v in allw["share_hi_exposure"]], marker="s", ms=3,
            lw=1.1, color="#8a8f98", label="All workers")
    ax.set_ylabel("Share in $\\beta \\geq 0.5$ groups (%)")
    ax.set_ylim(0, None)
    ax.set_title("(b) High-exposure employment by age", fontsize=9)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
        ax.set_xlabel("Age band")

    fig.text(0.99, 0.01, "PRELIMINARY — LLM-only scores (D6); not for publication",
             ha="right", va="bottom", fontsize=6, color="#b03a2e", style="italic")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(figures_dir / f"fig6_1_entry_rung_PRELIMINARY.{ext}",
                    bbox_inches="tight")
    plt.close(fig)

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRELIMINARY per D6",
        "source": "plfs_exposure_PRELIMINARY.parquet (PLFS 2023-24, principal status, weight=mult/no_qtr)",
        "exhibit": "6.1 entry-rung exposure gradient (Section 6 opener)",
    }
    (figures_dir / "fig6_1_entry_rung_PRELIMINARY.meta.json").write_text(json.dumps(meta, indent=2))
    print(tab.filter(pl.col("segment") == "white_collar"))
    event_study()
    print("figure + table written")


# ---------------------------------------------------------------------------
# Exhibit 6.2 — the canaries event study (ANALYSIS_PLAN §5)
# Panel: EPFO head x month x age cohort, net payroll additions, Apr 2020-Jul 2025.
# Treatment: head-level exposure score E (config/epfo_nic_crosswalk.yaml
# assignment; outputs/tables/epfo_head_exposure_PRELIMINARY.csv).
# Outcome: asinh(net additions) (industry tables publish net only; negatives
# legitimate). Young cohort = 18-25; comparison = 29+; 26-28 buffer excluded.
# Post = Nov 2022. SEs clustered by head (16 clusters - thin; stated).
# ---------------------------------------------------------------------------

YOUNG = ["18-21", "22-25"]
OLDER = ["29-35", ">35"]
POST_START = "2022-11"


def _event_panel() -> "pl.DataFrame":
    import numpy as np

    epfo = pl.read_parquet(processed_dir() / "epfo_payroll.parquet")
    heads = pl.read_csv(outputs_dir() / "tables" / "epfo_head_exposure_PRELIMINARY.csv")
    panel = (
        epfo.filter(pl.col("industry").is_not_null()
                    & pl.col("age_band").is_in(YOUNG + OLDER))
        .with_columns(pl.when(pl.col("age_band").is_in(YOUNG)).then(pl.lit("young"))
                      .otherwise(pl.lit("older")).alias("cohort"))
        .group_by("industry", "data_month", "cohort")
        .agg(pl.col("value").sum().alias("net"))
        .join(heads.select("industry", pl.col("mean_beta").alias("E")), on="industry", how="inner")
        .with_columns(
            (pl.col("data_month") >= POST_START).cast(pl.Int8).alias("post"),
            pl.col("net").map_elements(lambda x: float(np.arcsinh(x)), return_dtype=pl.Float64).alias("asinh_net"),
            (pl.col("data_month").str.slice(0, 4) + "Q" +
             ((pl.col("data_month").str.slice(5, 2).cast(pl.Int32) - 1) // 3 + 1).cast(pl.Utf8)).alias("quarter"),
        )
    )
    return panel


def event_study() -> None:
    import pyfixest as pf

    panel = _event_panel().to_pandas()
    young = panel[panel.cohort == "young"].copy()
    young["ExPost"] = young.E * young.post

    m1 = pf.feols("asinh_net ~ ExPost | industry + data_month", data=young,
                  vcov={"CRV1": "industry"})

    panel["y"] = (panel.cohort == "young").astype(int)
    panel["ExPostxY"] = panel.E * panel.post * panel.y
    panel["hm"] = panel.industry + "_" + panel.data_month
    panel["hy"] = panel.industry + "_" + panel.y.astype(str)
    panel["my"] = panel.data_month + "_" + panel.y.astype(str)
    m2 = pf.feols("asinh_net ~ ExPostxY | hm + hy + my", data=panel,
                  vcov={"CRV1": "industry"})

    # quarterly event-study coefficients on the young panel, ref 2022Q4
    q = sorted(young.quarter.unique())
    ref = "2022Q4"
    young["qcat"] = young.quarter
    m3 = pf.feols(f"asinh_net ~ i(qcat, E, ref='{ref}') | industry + data_month",
                  data=young, vcov={"CRV1": "industry"})
    coefs = m3.coef().rename("b").to_frame().join(m3.se().rename("se"))
    coefs = coefs[coefs.index.str.contains("qcat")]
    coefs["quarter"] = [s.split("[T.")[-1].rstrip("]") if "[T." in s else s.split("::")[1].split("]")[0]
                        for s in coefs.index]

    tables = outputs_dir() / "tables"
    with open(tables / "tab6_2_event_study_PRELIMINARY.txt", "w") as f:
        f.write("PRELIMINARY (D6) - canaries event study\n\n== DiD (young cohort) ==\n")
        f.write(m1.summary() or str(m1.tidy())); f.write("\n\n== Triple diff ==\n")
        f.write(str(m2.tidy())); f.write("\n\n== Quarterly event study (young) ==\n")
        f.write(str(coefs[["quarter", "b", "se"]]))
    print("== DiD young: E x Post =="); print(m1.tidy())
    print("== Triple diff: E x Post x Young =="); print(m2.tidy())

    # figure: quarterly coefficients
    plt.rcParams.update(STYLE)
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    cq = coefs.sort_values("quarter")
    xs = range(len(cq))
    ax.axhline(0, color="#999", lw=0.7)
    ax.axvline(list(cq.quarter).index("2023Q1") - 0.5 if "2023Q1" in list(cq.quarter) else 0,
               color="#b03a2e", lw=0.8, ls="--")
    ax.errorbar(xs, cq.b, yerr=1.96 * cq.se, fmt="o", ms=3.5, lw=1.1,
                color="#1f3b6e", capsize=2)
    ax.set_xticks(list(xs)); ax.set_xticklabels(cq.quarter, rotation=60, ha="right", fontsize=6.5)
    ax.set_ylabel("Coef. on Exposure x quarter\n(asinh net young additions)")
    fig.text(0.99, 0.01, "PRELIMINARY - LLM-only scores (D6); not for publication",
             ha="right", va="bottom", fontsize=6, color="#b03a2e", style="italic")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(outputs_dir() / "figures" / f"fig6_2_event_study_PRELIMINARY.{ext}",
                    bbox_inches="tight")
    plt.close(fig)
    print("figure + table written")


if __name__ == "__main__":
    main()
