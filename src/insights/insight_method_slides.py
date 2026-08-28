"""Methodology slide deck — 8 cards (title + 7 steps) in the Substack house
style. 16:9 PNGs at 300 dpi -> outputs/substack/method_slides/.
PRELIMINARY per D6; each card carries the source line.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from atlas_common import outputs_dir
from insights._style import (GRID, INK, INK_2, MUTED, SB_BLACK, SB_GOLD,
                             SB_GREY, SB_RED, SURFACE, apply_style)

OUT = outputs_dir() / "substack" / "method_slides"
SRC = ("Source: NCO-2015 Vol II (DGE) · PLFS 2023-24 (MoSPI) · EPFO payroll · NAS Statement 4A; "
       "preliminary LLM scoring; author's calculations.")


def slide(n_total, step, headline, subtitle, draw, fname):
    fig, ax = plt.subplots(figsize=(10, 5.625))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 56.25)
    ax.axis("off")
    eyebrow = "THE AI EXPOSURE ATLAS - METHODOLOGY" if step is None else \
        f"METHODOLOGY - STEP {step} OF 7"
    ax.text(4, 52.5, eyebrow, fontsize=8.5, color=MUTED, fontweight="bold")
    if step is not None:
        ax.text(96, 52.5, "".join("●" if i <= step else "○" for i in range(1, 8)),
                fontsize=9, color=SB_RED, ha="right")
    ax.text(4, 47.5, headline, fontsize=19, color=INK, fontweight="bold", va="top")
    ax.text(4, 41.5, subtitle, fontsize=10.5, color=INK_2, va="top", linespacing=1.45)
    draw(ax)
    ax.text(4, 1.6, SRC, fontsize=6.6, color=MUTED)
    ax.text(96, 1.6, "PRELIMINARY (D6)", fontsize=6.6, color=SB_RED, ha="right",
            style="italic")
    fig.savefig(OUT / fname, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def box(ax, x, y, w, h, text, fc, tc="white", fs=9, sub=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6",
                                fc=fc, ec="none"))
    ax.text(x + w / 2, y + h / 2 + (1.4 if sub else 0), text, ha="center",
            va="center", fontsize=fs, color=tc, fontweight="bold")
    if sub:
        ax.text(x + w / 2, y + h / 2 - 2.4, sub, ha="center", va="center",
                fontsize=7.2, color=tc, alpha=0.92)


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=13, color=MUTED, lw=1.2))


def d_title(ax):
    steps = [("NCO-2015\ndictionary", SB_GREY), ("18,622\ntasks", SB_BLACK),
             ("E0/E1/E2\nscores", SB_RED), ("122 group\nE-scores", SB_RED),
             ("463M PLFS\nworkers", SB_BLACK), ("The Atlas", SB_GOLD),
             ("EPFO\ncanaries", SB_GREY)]
    x = 4
    for i, (t, c) in enumerate(steps):
        box(ax, x, 14, 10.8, 9, t, c, fs=8)
        if i < len(steps) - 1:
            arrow(ax, x + 11.6, 18.5, x + 13.1, 18.5)
        x += 13.7
    ax.text(4, 8.5, "Every arrow is a script; every number regenerates from the public repo.",
            fontsize=9, color=INK_2, style="italic")


def d_step1(ax):
    box(ax, 6, 12, 26, 18, "NCO-2015 Vol II", SB_GREY, fs=11,
        sub="3,442 occupation entries\n(DGE, Govt of India)")
    arrow(ax, 34, 21, 42, 21)
    box(ax, 44, 12, 50, 18, "18,622 task statements", SB_BLACK, fs=11,
        sub='"Examines vehicle to ascertain nature and location of defects..."\n'
            "one duty sentence = one unit of analysis")


def d_step2(ax):
    ax.text(50, 28.5, '"Could an LLM - or LLM-powered software -\n'
            'halve this task at equal quality?"', ha="center", fontsize=12.5,
            color=INK, fontweight="bold", linespacing=1.5)
    shares = [("E0 - not exposed", 83, SB_GREY), ("E1 - chat", 10, SB_RED),
              ("E2 - tooling", 6, SB_GOLD)]
    x = 6.0
    for lab, pct, c in shares:
        w = pct * 0.85
        box(ax, x, 13, w, 7, f"{pct}%" if pct < 15 else f"{lab}  {pct}%", c,
            fs=9 if pct > 15 else 8)
        if pct < 15:
            ax.text(x + w / 2, 10.2, lab, ha="center", fontsize=7.6, color=c,
                    fontweight="bold")
        x += w + 1.4
    ax.text(4, 5.6, "claude-sonnet-4-6, temperature 0, fixed public rubric; 99.85% valid labels; "
            "human validation gate pending (D6).", fontsize=8, color=INK_2)


def d_step3(ax):
    ax.text(6, 30, "α = share(E1)          β = share(E1) + ½ · share(E2)          ζ = share(E1) + share(E2)",
            fontsize=11.5, color=INK, fontweight="bold")
    box(ax, 6, 10, 88, 12,
        "Software developers (139 tasks):  64.0% E1, 19.4% E2", SB_RED, fs=10.5,
        sub="α = 0.640      β = 0.640 + ½ × 0.194 = 0.737      ζ = 0.835")


def d_step4(ax):
    box(ax, 6, 14, 26, 16, "122 group\nE-scores", SB_RED, fs=10)
    ax.text(36.5, 22, "×", fontsize=18, color=INK_2, ha="center")
    box(ax, 41, 14, 26, 16, "PLFS 2023-24\n164,523 workers", SB_BLACK, fs=10)
    arrow(ax, 68.5, 22, 74, 22)
    box(ax, 75, 14, 20, 16, "463M workers\nmapped", SB_GOLD, fs=10)
    ax.text(4, 8, "weight = (MULT/100 if NSS = NSC else MULT/200) / NO_QTR   ->   99.4% employment coverage; "
            "mean E = 0.086", fontsize=8.5, color=INK_2, family="monospace")


def d_step5(ax):
    ax.text(6, 31, "asinh(net additions) = γ·(E × Post) + industry FE + month FE",
            fontsize=11.5, color=INK, fontweight="bold", family="monospace")
    box(ax, 6, 12, 42, 12, "88-month EPFO panel", SB_GREY, fs=10,
        sub="Sep 2017 - Jul 2025 · age bands x industry\nflow identity holds exactly")
    box(ax, 52, 12, 42, 12, "Young (18-25) vs 29+", SB_RED, fs=10,
        sub="exposure x post-ChatGPT · 16 industry heads\npoint estimates negative, not significant")


def d_step6(ax):
    import numpy as np
    rng = np.random.default_rng(42)
    clusters = [(0.65, 30, SB_RED, "Frontier (11M)"), (0.38, 22, SB_GOLD, "Paperwork (10M)"),
                (0.2, 27, "#0072B2", "Managers/teachers (40M)"), (0.06, 34, "#3D8B37", "Agrarian (232M)"),
                (0.09, 16, "#7C5CB0", "Urban manual (170M)")]
    for cx, cy, c, lab in clusters:
        xs = cx * 90 + 5 + rng.normal(0, 2.2, 14)
        ys = cy + rng.normal(0, 2.2, 14)
        ax.scatter(xs, ys, s=26, c=c, alpha=0.65, edgecolors="white", linewidths=0.5)
        ax.text(cx * 90 + 5, cy - 6.2, lab, ha="center", fontsize=7.6, color=INK_2)
    ax.text(4, 7, "k-means on 7 features (exposure mix, education, earnings, gender, age, location); "
            "k = 5 by silhouette.", fontsize=8.5, color=INK_2)


def d_step7(ax):
    stats = [("Share of workers", "mean E 0.086", SB_BLACK),
             ("Share of pay", "mean E 0.155", SB_RED),
             ("Share of value-add", "mean E 0.146", SB_GOLD)]
    x = 6
    for lab, val, c in stats:
        box(ax, x, 16, 26, 14, lab, c, fs=10, sub=val)
        if x < 60:
            arrow(ax, x + 27, 23, x + 30, 23)
        x += 31
    ax.text(4, 8.5, "Industries with above-average exposure produce 57% of GVA; ~3% of GVA flows through "
            "high-exposure labour.\nRefused: any \"GDP at risk\" multiplication - that is a forecast, not a measurement.",
            fontsize=8.5, color=INK_2, linespacing=1.5)


def main() -> None:
    apply_style()
    OUT.mkdir(parents=True, exist_ok=True)
    slide(8, None, "From India's own dictionary of work to its AI atlas",
          "Seven steps, one pipeline: parse - score - aggregate - project - test - cluster - value.\n"
          "Built on NCO-2015 task content, not a crosswalk from US O*NET.",
          d_title, "slide_0_pipeline.png")
    slide(8, 1, "Start where India defines work",
          "The government's own occupation dictionary describes every job as a paragraph of duties.\n"
          "We split those paragraphs into single-duty sentences - the unit everything else is built on.",
          d_step1, "slide_1_tasks.png")
    slide(8, 2, "One question, asked 18,622 times",
          "Each task statement is scored against a fixed written rubric (adapted from Eloundou et al. 2024\n"
          "with India-specific rules: multilingual work is not protection; cash and field presence are).",
          d_step2, "slide_2_scoring.png")
    slide(8, 3, "From task labels to an occupation's score",
          "Three standard aggregations turn labels into a 0-1 exposure score per occupation;\n"
          "β - the headline - counts tooling-dependent tasks at half weight.",
          d_step3, "slide_3_aggregation.png")
    slide(8, 4, "Project onto 463 million workers",
          "Each PLFS worker inherits their occupation group's score; official survey weights\n"
          "turn 164,523 respondents into national estimates.",
          d_step4, "slide_4_plfs.png")
    slide(8, 5, "Then watch the payroll",
          "Does young hiring fall in exposed industries after ChatGPT? EPFO's monthly payroll\n"
          "is the test bed; the honest answer so far: a power-limited, uniformly negative null.",
          d_step5, "slide_5_epfo.png")
    slide(8, 6, "Let the data draw its own map",
          "Clustering the 122 occupation groups sorts India's workforce into five AI worlds -\n"
          "and rediscovers the chat-vs-tooling distinction without being told it exists.",
          d_step6, "slide_6_typology.png")
    slide(8, 7, "Three weightings: crowd, paycheque, value-add",
          "The same index, weighted three ways, is the whole story: exposure is rare among workers,\n"
          "concentrated in pay, and central to where India's value-add is produced.",
          d_step7, "slide_7_gva.png")
    print("8 slides written to", OUT)


if __name__ == "__main__":
    main()
