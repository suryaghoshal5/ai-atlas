"""Waterfall: how 18,622 NCO task statements were classified (PRELIMINARY, D6).

Flow: parsed -> unresolved dropout -> scored -> E0 (not exposed) -> exposed
remainder split into E1 (chat alone) and E2 (needs tooling), stepping to zero.
"""

from __future__ import annotations

from datetime import date

import matplotlib.pyplot as plt
import polars as pl

from atlas_common import outputs_dir, processed_dir
from insights._style import (SB_BLACK, SB_GOLD, SB_GREY, SB_RED, add_source,
                             apply_style, head_sub)

OUT = outputs_dir() / "substack"
DATASET = "NCO-2015 Vol II task statements x adapted Eloundou rubric (preliminary LLM scoring)"


def main() -> None:
    apply_style()
    OUT.mkdir(parents=True, exist_ok=True)
    scores = pl.read_parquet(OUT.parent / "full_batch_scoring" / "task_scores_full_PRELIMINARY.parquet")
    tasks = pl.read_parquet(processed_dir() / "task_statements_full.parquet")
    n_parsed = tasks.height
    counts = dict(scores.group_by("score").len().iter_rows())
    n_e0, n_e1, n_e2 = counts["E0"], counts["E1"], counts["E2"]
    n_scored = scores.height
    n_unres = n_parsed - n_scored

    # waterfall segments: (label, delta, color); running level tracks the top
    segs = [
        ("Task statements\nparsed from\nNCO-2015 Vol II", n_parsed, SB_GREY),
        ("Unresolved\n(refused/format,\n0.15%)", -n_unres, "#c9c7c0"),
        ("Scored", None, SB_GREY),  # subtotal bar
        ("E0 - not\nexposed", -n_e0, SB_BLACK),
        ("E1 - exposed,\nchat alone", -n_e1, SB_RED),
        ("E2 - exposed,\nneeds tooling", -n_e2, SB_GOLD),
    ]
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    level = 0.0
    for i, (lab, delta, color) in enumerate(segs):
        if delta is None:  # subtotal: full bar from 0 to current level
            ax.bar(i, level, bottom=0, color=SB_GREY, width=0.62, alpha=0.55)
            ax.text(i, level + 300, f"{int(level):,}", ha="center", fontsize=9.5,
                    fontweight="bold", color=SB_GREY)
            continue
        if delta >= 0:
            bottom, height, top = level, delta, level + delta
        else:
            bottom, height, top = level + delta, -delta, level
        ax.bar(i, height, bottom=bottom, color=color, width=0.62)
        ax.text(i, top + 300, f"{delta:+,}" if i else f"{delta:,}", ha="center",
                fontsize=9.5, fontweight="bold", color=color if color != "#c9c7c0" else SB_GREY)
        new_level = level + delta
        # connector to the next bar
        if i < len(segs) - 1:
            ax.plot([i + 0.31, i + 0.69], [new_level, new_level],
                    color="#b9b7b0", lw=0.9, ls=":")
        level = new_level
    ax.set_xticks(range(len(segs)))
    ax.set_xticklabels([s[0] for s in segs], fontsize=7.6)
    ax.set_ylabel("Task statements")
    ax.set_ylim(0, n_parsed * 1.12)
    pct = lambda n: f"{n / n_scored:.0%}"
    head_sub(ax, "Five in six Indian job tasks are beyond today's AI\n"
                 f"18,622 task statements scored: {pct(n_e0)} not exposed (E0), {pct(n_e1)} doable by\n"
                 f"a chat LLM alone (E1), {pct(n_e2)} doable with LLM-powered software (E2).\n"
                 "Rubric adapted from Eloundou et al. (2024). PLFS-independent; NCO-2015.")
    add_source(fig, DATASET)
    fig.savefig(OUT / "insight_task_waterfall.png", bbox_inches="tight")
    plt.close(fig)

    prov = OUT / "provenance.md"
    existing = prov.read_text() if prov.exists() else "# Substack chart provenance\n\n"
    prov.write_text(existing + f"### insight_task_waterfall ({date.today()})\n"
                    f"parsed {n_parsed}; unresolved {n_unres}; scored {n_scored}; "
                    f"E0 {n_e0}; E1 {n_e1}; E2 {n_e2}\nSource: {DATASET}.\n")
    print("waterfall written")


if __name__ == "__main__":
    main()
