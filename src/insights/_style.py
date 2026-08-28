"""Surya's Substack house style for matplotlib charts (per substack_chart skill).

Palette, bold-headline + grey-subtitle titles, self-contained source lines.
Static PNG @ 300 dpi on the light surface.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SB_RED = "#C8102E"
SB_BLACK = "#1a1a1a"
SB_GREY = "#8a8781"
SB_GOLD = "#eda100"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "savefig.dpi": 300,
        "figure.dpi": 120,
        "font.family": "sans-serif",
        "text.color": INK,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK_2,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "axes.titlelocation": "left",
    })


def head_sub(ax, title, fontsize=12, loc="left", **_kw):
    """Bold headline (before first newline) + grey normal-weight subtitle."""
    head, _, sub = title.partition("\n")
    nl = (sub.count("\n") + 1) if sub else 0
    ss = fontsize - 1
    ax.set_title(head, loc=loc, fontweight="bold", fontsize=fontsize + 0.5,
                 pad=(nl * ss * 1.5 + 7) if sub else 6)
    if sub:
        ax.text(0.0, 1.0, sub, transform=ax.transAxes, ha="left", va="bottom",
                fontsize=ss, color=INK_2, linespacing=1.3, fontweight="normal")


def fig_head_sub(fig, title, fontsize=12.5, top=0.99, gap=0.075):
    """head_sub at FIGURE level, for multi-panel figures where an axes-level
    title would run under its neighbour. Panels then carry short bold titles."""
    head, _, sub = title.partition("\n")
    fig.text(0.01, top, head, ha="left", va="top", fontweight="bold",
             fontsize=fontsize + 0.5, color=INK)
    if sub:
        fig.text(0.01, top - gap, sub, ha="left", va="top", fontsize=fontsize - 1,
                 color=INK_2, linespacing=1.35)


def add_source(fig, dataset: str, y: float = -0.045) -> None:
    # negative y sits below the axis labels; bbox_inches="tight" expands to fit.
    # Charts with rotated tick labels need a lower y (e.g. -0.18).
    fig.text(0.01, y, f"Source: {dataset}; author's calculations.",
             ha="left", va="top", fontsize=7.5, color=MUTED)
