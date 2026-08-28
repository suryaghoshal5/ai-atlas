"""Substack claim charts for the AI Exposure Atlas storyline (six claims).

Numbers are PRELIMINARY per D6 (LLM-only scores) — the source line says so.
Outputs: outputs/substack/insight_*.png + provenance.md.
"""

from __future__ import annotations

from datetime import date

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import polars as pl

from atlas_common import outputs_dir, processed_dir
from atlas_common.education import BANDS, check_codes
from insights._style import (SB_BLACK, SB_GOLD, SB_GREY, SB_RED, SURFACE,
                             add_source, apply_style, fig_head_sub, head_sub)

OUT = outputs_dir() / "substack"
DATASET = "PLFS 2023-24 unit data x NCO-2015 task-exposure index (preliminary LLM scoring)"
PROV: list[str] = []

STATE_NAMES = {7: "Delhi", 32: "Kerala", 6: "Haryana", 36: "Telangana",
               27: "Maharashtra", 29: "Karnataka", 33: "Tamil Nadu",
               5: "Uttarakhand", 21: "Odisha", 23: "Madhya Pradesh",
               22: "Chhattisgarh", 10: "Bihar"}


def _df() -> pl.DataFrame:
    return (pl.read_parquet(processed_dir() / "plfs_exposure_PRELIMINARY.parquet")
            .filter(pl.col("beta").is_not_null())
            .with_columns(pl.col("group3").str.slice(0, 1).alias("div")))


def _wmean(s: pl.DataFrame) -> float:
    return float((s["beta"] * s["weight"]).sum() / s["weight"].sum())


def _save(fig, name: str, numbers: str) -> None:
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight")
    plt.close(fig)
    PROV.append(f"### {name} ({date.today()})\n{numbers}\nSource: {DATASET}.\n")


def chart_rare(df: pl.DataFrame) -> None:
    W = float(df["weight"].sum())
    bins = [(0, .05), (.05, .1), (.1, .2), (.2, .3), (.3, .4), (.4, .5), (.5, 1.01)]
    labels = ["0-.05", ".05-.10", ".10-.20", ".20-.30", ".30-.40", ".40-.50", ".50+"]
    shares = [float(df.filter((pl.col("beta") >= a) & (pl.col("beta") < b))["weight"].sum() / W) * 100
              for a, b in bins]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    colors = [SB_GREY] * 6 + [SB_RED]
    ax.bar(labels, shares, color=colors, width=0.7)
    for i, v in enumerate(shares):
        ax.text(i, v + 0.8, f"{v:.0f}%", ha="center", fontsize=9,
                color=SB_RED if i == 6 else SB_GREY, fontweight="bold")
    head_sub(ax, "AI can barely touch most Indian jobs\n"
                 "Share of workers by occupation exposure score; red: high exposure\n"
                 "(score 0.5+) - under 2% of workers. PLFS 2023-24.")
    ax.set_xlabel("Exposure score of worker's occupation (0-1)")
    ax.set_ylabel("% of employed workers")
    ax.set_ylim(0, 55)
    add_source(fig, DATASET)
    _save(fig, "insight_exposure_rare",
          "bin shares %: " + ", ".join(f"{l}={s:.1f}" for l, s in zip(labels, shares)))


def chart_money(df: pl.DataFrame) -> None:
    W = float(df["weight"].sum())
    hc = float(df.filter(pl.col("beta") >= 0.5)["weight"].sum() / W) * 100
    e = df.filter(pl.col("monthly_earnings") > 0)
    wb_t = float((e["monthly_earnings"] * e["weight"]).sum())
    wb = float(e.filter(pl.col("beta") >= 0.5)
               .select(pl.col("monthly_earnings") * pl.col("weight")).sum().item() / wb_t) * 100
    fig, ax = plt.subplots(figsize=(6.2, 4))
    ax.bar(["Share of workers", "Share of wage bill"], [hc, wb],
           color=[SB_BLACK, SB_RED], width=0.5)
    for i, v in enumerate([hc, wb]):
        ax.text(i, v + 0.15, f"{v:.1f}%", ha="center", fontsize=13, fontweight="bold",
                color=[SB_BLACK, SB_RED][i])
    head_sub(ax, "AI exposure follows the money, not the crowd\n"
                 "High-exposure occupations (score 0.5+) hold 1.9% of India's workers\n"
                 "but 7.1% of its wage bill. PLFS 2023-24; salaried + self-employed earnings.")
    ax.set_ylabel("% of national total")
    ax.set_ylim(0, 8.5)
    add_source(fig, DATASET)
    _save(fig, "insight_wagebill", f"headcount {hc:.1f}%, wage bill {wb:.1f}% (beta>=0.5)")


def _wshare(s: pl.DataFrame, total: float) -> float:
    return float(s["weight"].sum()) / total * 100


def chart_education(df: pl.DataFrame) -> None:
    """Exposure by education rung, with the labour-force share behind it.

    Bands come from atlas_common.education — the NSS ladder, with graduate (12)
    and postgraduate (13) kept apart, since the whole claim of this exhibit is
    that exposure switches on at a specific rung.
    """
    check_codes(df["edu_code"].unique().to_list())
    W = float(df["weight"].sum())
    names, means, shares = [], [], []
    for name, codes in BANDS:
        s = df.filter(pl.col("edu_code").is_in(codes))
        if not s.height:
            continue
        names.append(name)
        means.append(_wmean(s))
        shares.append(_wshare(s, W))
    nat = _wmean(df)
    xs = list(range(len(names)))

    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    colors = [SB_RED if m > nat else SB_GREY for m in means]
    ax.bar(xs, means, color=colors, width=0.62)
    ax.axhline(nat, color=SB_GOLD, lw=1.4, ls="--")
    halo = [pe.withStroke(linewidth=2.6, foreground=SURFACE)]
    for i, m in enumerate(means):
        ax.text(i, m + 0.004, f"{m:.2f}", ha="center", fontsize=9,
                fontweight="bold", color=colors[i], path_effects=halo)
    # drawn after the bar labels, haloed: the average line runs through the
    # short left-hand bars, so whichever text lands on top must stay readable
    ax.text(0.02, nat + max(means) * 0.03, f"national avg {nat:.2f}", fontsize=8.5,
            color="#a67102", ha="left", transform=ax.get_yaxis_transform(),
            path_effects=halo)
    ax.set_xticks(xs)
    ax.set_xticklabels(names)
    ax.set_ylabel("Mean exposure score, 0-1 (bars, left)")
    ax.set_xlabel("Worker's general education level")
    ax.set_ylim(0, max(means) * 1.25)

    # Labour-force share on the right axis. Two scales on one chart is a
    # readability compromise, taken deliberately: the point of the exhibit is
    # that the exposed rungs are the thin ones, and that only reads when both
    # series sit over the same bars.
    ax2 = ax.twinx()
    ax2.plot(xs, shares, color=SB_BLACK, lw=1.8, marker="o", ms=5.5,
             mfc=SURFACE, mew=1.4, zorder=5, label="% of employed workers (right)")
    ax2.set_ylabel("% of employed workers (line, right)")
    ax2.set_ylim(0, max(shares) * 1.35)
    ax2.grid(False)
    # direct-label only the peak and the two degree rungs — not every point
    to_label = {shares.index(max(shares))}
    to_label |= {i for i, n in enumerate(names) if n in ("Graduate", "Postgraduate+")}
    for i in sorted(to_label):
        ax2.annotate(f"{shares[i]:.0f}%", (i, shares[i]), textcoords="offset points",
                     xytext=(0, 9), ha="center", fontsize=8.5, color=SB_BLACK,
                     path_effects=halo)
    ax2.legend(frameon=False, fontsize=8.5, loc="upper center")

    head_sub(ax, "AI exposure is a graduate phenomenon\n"
                 "Mean exposure score by education (bars, red: above national average)\n"
                 "against each rung's share of all employed workers (line). PLFS 2023-24.")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    add_source(fig, DATASET, y=-0.18)
    # band names contain commas, so provenance fields are semicolon-separated
    _save(fig, "insight_education",
          "means: " + "; ".join(f"{n}={m:.3f}" for n, m in zip(names, means))
          + f" | nat={nat:.3f} | labour-force shares %: "
          + "; ".join(f"{n}={v:.1f}" for n, v in zip(names, shares)))


def chart_gender(df: pl.DataFrame) -> None:
    """Mean exposure AND high-exposure incidence, economy-wide vs organised.

    The incidence panel exists because the white paper's "one in five
    organised-sector women works in a high-exposure occupation, vs one in six
    men" had nothing computing it — this chart carried the four means only, so
    the claim was untraceable (Golden Rule 1). Incidence is the survey-weighted
    share of each group working in an occupation scoring beta >= 0.5.
    """
    org = (pl.col("sector_code") == 2) & (pl.col("formal_proxy") == True)  # noqa: E712
    cuts = [("All workers", pl.lit(True)),
            ("Organised sector\n(urban + benefits)", org)]

    def _hi(s: pl.DataFrame) -> float:
        w = float(s["weight"].sum())
        return float(s.filter(pl.col("beta") >= 0.5)["weight"].sum()) / w * 100 if w else 0.0

    def by_sex(fn) -> tuple[list[float], list[float]]:
        men = [fn(df.filter(cut & (pl.col("sex_code") == 1))) for _, cut in cuts]
        women = [fn(df.filter(cut & (pl.col("sex_code") == 2))) for _, cut in cuts]
        return men, women

    men_beta, women_beta = by_sex(_wmean)
    men_hi, women_hi = by_sex(_hi)

    fig, axes = plt.subplots(1, 2, figsize=(9.8, 4.8))
    x, w = [0, 1], 0.32
    panels = [
        (axes[0], men_beta, women_beta, "Mean exposure score (0-1)",
         "Mean exposure score", lambda v: f"{v:.2f}", 1.20),
        (axes[1], men_hi, women_hi, "% in high-exposure occupations",
         "Share in high-exposure occupations (score 0.5+)",
         lambda v: f"{v:.0f}%\n1 in {round(100 / v)}" if v else "0%", 1.34),
    ]
    for ax, men, women, ylabel, panel_title, fmt, headroom in panels:
        ax.bar([i - w / 2 for i in x], men, width=w, color=SB_BLACK, label="Men")
        ax.bar([i + w / 2 for i in x], women, width=w, color=SB_RED, label="Women")
        top = max(men + women) or 1.0   # a cut with no high-exposure workers
        for i in x:
            ax.text(i - w / 2, men[i] + top * 0.025, fmt(men[i]), ha="center",
                    fontsize=9.5, fontweight="bold", color=SB_BLACK, linespacing=1.25)
            ax.text(i + w / 2, women[i] + top * 0.025, fmt(women[i]), ha="center",
                    fontsize=9.5, fontweight="bold", color=SB_RED, linespacing=1.25)
        ax.set_xticks(x)
        ax.set_xticklabels([label for label, _ in cuts])
        ax.set_ylabel(ylabel)
        ax.set_ylim(0, top * headroom)
        ax.set_title(panel_title, loc="left", fontsize=9.5, color=SB_GREY, pad=8)

    fig_head_sub(fig, "Inside the organised sector, the gender gap flips\n"
                      "Black: men, red: women. Economy-wide women's jobs are less exposed;\n"
                      "among urban workers with benefits, more — and more of those women\n"
                      "sit in the most exposed occupations outright. PLFS 2023-24.")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", bbox_to_anchor=(0.995, 1.0),
               ncol=2, frameon=False, fontsize=9)
    fig.subplots_adjust(top=0.70, wspace=0.28)
    add_source(fig, DATASET, y=0.005)
    _save(fig, "insight_gender_flip",
          f"mean beta: all M={men_beta[0]:.3f} F={women_beta[0]:.3f}; "
          f"organised M={men_beta[1]:.3f} F={women_beta[1]:.3f}; "
          f"share in beta>=0.5 %: all M={men_hi[0]:.1f} F={women_hi[0]:.1f}; "
          f"organised M={men_hi[1]:.1f} F={women_hi[1]:.1f}")


def chart_entry_rung(df: pl.DataFrame) -> None:
    wc = df.filter(pl.col("div").is_in(["1", "2", "3", "4"]))
    bands = [(20, 24), (25, 29), (30, 34), (35, 39), (40, 44), (45, 49), (50, 54), (55, 59)]
    hi = [float(wc.filter((pl.col("age") >= a) & (pl.col("age") <= b) & (pl.col("beta") >= 0.5))
                ["weight"].sum() /
                wc.filter((pl.col("age") >= a) & (pl.col("age") <= b))["weight"].sum()) * 100
          for a, b in bands]
    labels = [f"{a}-{b}" for a, b in bands]
    avg = float(wc.filter(pl.col("beta") >= 0.5)["weight"].sum() / wc["weight"].sum()) * 100
    fig, ax = plt.subplots(figsize=(7, 4.2))
    colors = [SB_RED if v > avg else SB_GREY for v in hi]
    ax.bar(labels, hi, color=colors, width=0.68)
    ax.axhline(avg, color=SB_GOLD, lw=1.4, ls="--")
    ax.text(len(bands) - 0.45, avg + 0.4, f"white-collar avg {avg:.0f}%", fontsize=8.5,
            color="#a67102", ha="right")
    for i, v in enumerate(hi):
        ax.text(i, v + 0.4, f"{v:.0f}%", ha="center", fontsize=9, fontweight="bold",
                color=colors[i])
    head_sub(ax, "India's freshest workers hold its most exposed jobs\n"
                 "Share of white-collar workers in high-exposure occupations (score 0.5+)\n"
                 "by age; red: above the white-collar average. PLFS 2023-24.")
    ax.set_xlabel("Age band")
    ax.set_ylabel("% in high-exposure occupations")
    add_source(fig, DATASET)
    _save(fig, "insight_entry_rung",
          "hi-share % by band: " + ", ".join(f"{l}={v:.1f}" for l, v in zip(labels, hi))
          + f"; wc avg={avg:.1f}")


def chart_states(df: pl.DataFrame) -> None:
    W = float(df["weight"].sum())
    nat = _wmean(df)
    st = (df.group_by("state")
          .agg(((pl.col("beta") * pl.col("weight")).sum() / pl.col("weight").sum()).alias("mb"),
               pl.col("weight").sum().alias("w"))
          .filter(pl.col("w") / W > 0.005).sort("mb", descending=True))
    top = st.head(8).to_dicts()
    bot = st.tail(4).to_dicts()
    rows = top + [None] + bot
    names, vals = [], []
    for r in rows:
        if r is None:
            names.append("...")
            vals.append(0)
        else:
            names.append(STATE_NAMES.get(int(r["state"]), f"state {int(r['state'])}"))
            vals.append(r["mb"])
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    ypos = list(range(len(names)))[::-1]
    colors = [SB_RED if v > nat else SB_GREY for v in vals]
    ax.barh(ypos, vals, color=colors, height=0.62)
    ax.set_yticks(ypos)
    ax.set_yticklabels(names)
    ax.axvline(nat, color=SB_GOLD, lw=1.4, ls="--")
    ax.text(nat + 0.002, ypos[0] + 0.55, f"national avg {nat:.2f}", fontsize=8.5, color="#a67102")
    for y, v in zip(ypos, vals):
        if v:
            ax.text(v + 0.002, y, f"{v:.2f}", va="center", fontsize=8.5,
                    color=SB_RED if v > nat else SB_GREY, fontweight="bold")
    head_sub(ax, "AI exposure maps onto India's services geography\n"
                 "Mean exposure score by state (states over 0.5% of employment);\n"
                 "red: above national average. PLFS 2023-24.")
    ax.set_xlabel("Mean exposure score (0-1)")
    add_source(fig, DATASET)
    _save(fig, "insight_states",
          "; ".join(f"{n}={v:.3f}" for n, v in zip(names, vals) if v) + f"; nat={nat:.3f}")


def main() -> None:
    apply_style()
    OUT.mkdir(parents=True, exist_ok=True)
    df = _df()
    chart_rare(df)
    chart_money(df)
    chart_education(df)
    chart_gender(df)
    chart_entry_rung(df)
    chart_states(df)
    prov = OUT / "provenance.md"
    existing = prov.read_text() if prov.exists() else "# Substack chart provenance\n\n"
    prov.write_text(existing + "\n".join(PROV))
    print(f"6 charts written to {OUT}")


if __name__ == "__main__":
    main()
