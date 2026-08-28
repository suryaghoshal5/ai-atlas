"""Substack claim charts for the AI Exposure Atlas storyline (six claims).

Numbers are PRELIMINARY per D6 (LLM-only scores) — the source line says so.
Outputs: outputs/substack/insight_*.png + provenance.md.
"""

from __future__ import annotations

from datetime import date

import matplotlib.pyplot as plt
import polars as pl

from atlas_common import outputs_dir, processed_dir
from insights._style import (SB_BLACK, SB_GOLD, SB_GREY, SB_RED, add_source,
                             apply_style, head_sub)

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


def chart_education(df: pl.DataFrame) -> None:
    # PLFS manual C-19 codes: 01 not literate; 02-04 literate w/o schooling;
    # 05 below primary; 06 primary; 07 middle; 08 secondary; 10 higher
    # secondary; 11 diploma; 12 graduate; 13 postgraduate+.
    edu = [("Not literate", [1]), ("Below\nprimary", [2, 3, 4, 5]),
           ("Primary", [6]), ("Middle", [7]), ("Secondary", [8]),
           ("Higher\nsecondary", [10]), ("Diploma", [11]),
           ("Graduate", [12]), ("Post-\ngraduate+", [13])]
    W = float(df["weight"].sum())
    rows = []
    for n, codes in edu:
        s = df.filter(pl.col("edu_code").is_in(codes))
        w = float(s["weight"].sum())
        rows.append((n, w / W, float((s["beta"] * s["weight"]).sum() / w)))
    nat = float((df["beta"] * df["weight"]).sum() / W)
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    x = 0.0
    for n, share, e in rows:
        w = share * 100
        color = SB_RED if e > nat else SB_GREY
        ax.bar(x + w / 2, e, width=w - 0.45, color=color)
        if w > 3:
            ax.text(x + w / 2, e + 0.005, f"{e:.2f}", ha="center", fontsize=8,
                    fontweight="bold", color=color)
        rot = 0 if w > 9 else 90
        ax.text(x + w / 2, -0.012, n, ha="center", va="top", fontsize=7.2,
                color="#52514e", rotation=rot,
                linespacing=1.1) if rot == 0 else ax.text(
            x + w / 2, -0.018,
            n.replace("\n", " ") + (f"  ({e:.2f})" if w <= 3 else ""),
            ha="center", va="top", fontsize=6.4, color="#52514e",
            rotation=40, rotation_mode="anchor")
        if w > 5:
            ax.text(x + w / 2, 0.008, f"{share:.0%}", ha="center", fontsize=7,
                    color="white", fontweight="bold")
        x += w
    ax.axhline(nat, color=SB_GOLD, lw=1.4, ls="--")
    ax.text(1, nat + 0.005, f"national avg {nat:.2f}", fontsize=8.5, color="#a67102")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 0.27)
    ax.set_xticks([])
    head_sub(ax, "AI exposure is a graduate phenomenon\n"
                 "Mean exposure score by education; bar WIDTH = share of the workforce\n"
                 "(white %); red: above national average. Exposure climbs gently through\n"
                 "school, then doubles at graduation. PLFS 2023-24.")
    ax.set_ylabel("Mean exposure score (0-1)")
    add_source(fig, DATASET, y=-0.12)
    _save(fig, "insight_education",
          "; ".join(f"{n.replace(chr(10),' ')}: share={s:.3f}, E={e:.3f}" for n, s, e in rows)
          + f"; nat={nat:.3f}; CORRECTED bucket coding per manual C-19 (2026-08-28)")


def chart_gender(df: pl.DataFrame) -> None:
    org = (pl.col("sector_code") == 2) & (pl.col("formal_proxy") == True)  # noqa: E712
    groups = {
        "All workers": [ _wmean(df.filter(pl.col("sex_code") == 1)),
                         _wmean(df.filter(pl.col("sex_code") == 2))],
        "Organised sector\n(urban + benefits)": [_wmean(df.filter(org & (pl.col("sex_code") == 1))),
                                                 _wmean(df.filter(org & (pl.col("sex_code") == 2)))],
    }
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    x = [0, 1]
    w = 0.32
    men = [v[0] for v in groups.values()]
    women = [v[1] for v in groups.values()]
    ax.bar([i - w / 2 for i in x], men, width=w, color=SB_BLACK, label="Men")
    ax.bar([i + w / 2 for i in x], women, width=w, color=SB_RED, label="Women")
    for i in x:
        ax.text(i - w / 2, men[i] + .005, f"{men[i]:.2f}", ha="center", fontsize=10,
                fontweight="bold", color=SB_BLACK)
        ax.text(i + w / 2, women[i] + .005, f"{women[i]:.2f}", ha="center", fontsize=10,
                fontweight="bold", color=SB_RED)
    ax.set_xticks(x)
    ax.set_xticklabels(list(groups.keys()))
    head_sub(ax, "Inside the organised sector, the gender gap flips\n"
                 "Mean exposure score; black: men, red: women. Economy-wide women's jobs\n"
                 "are less exposed - among urban workers with benefits, more. PLFS 2023-24.")
    ax.set_ylabel("Mean exposure score (0-1)")
    ax.legend(frameon=False, fontsize=9)
    add_source(fig, DATASET)
    _save(fig, "insight_gender_flip",
          f"all M={men[0]:.3f} F={women[0]:.3f}; organised M={men[1]:.3f} F={women[1]:.3f}")


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
