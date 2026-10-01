"""Atlas film: a ~2.5 minute cinematic explainer of the LinkedIn essay
"Where does AI actually land in India?" (Sep 24, 2026), in a Nolan-style
grammar: black ground, one signal colour, 2.39:1 letterbox that opens to full
frame for the data reveals, section intertitles, a ticking clock that
accelerates and then stops.

Presentation layer only (like the rest of src/insights/): no paper number
depends on it. Every figure on screen is quoted from the published essay or
read from committed outputs:
    outputs/atlas_grid/atlas_grid_data.json          the 463-square grid (`make atlas-grid`)
    outputs/tables/tab6_2_event_study_PRELIMINARY.txt  the canary event study
The end card carries the PRELIMINARY stamp (D6).

Picture and score are both generated here (PIL + numpy/scipy, muxed by
ffmpeg); no stock footage or licensed audio.

    PYTHONPATH=src python -m insights.film                 # outputs/film/atlas_film.mp4
    PYTHONPATH=src python -m insights.film --stills 3,60,112   # PNG stills only
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
import wave
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from atlas_common import outputs_dir, run_seed

OUT = outputs_dir() / "film"
GRID_JSON = outputs_dir() / "atlas_grid" / "atlas_grid_data.json"
EVENT_TXT = outputs_dir() / "tables" / "tab6_2_event_study_PRELIMINARY.txt"

W, H, FPS = 1920, 1080, 30
SR = 48000
BAR = round((H - W / 2.39) / 2)  # 2.39:1 letterbox bar height

BG = (11, 11, 11)
INK = (236, 234, 228)
INK2 = (138, 136, 130)
INK3 = (70, 69, 66)
RED = (227, 6, 19)
# atlas grid bins (same breaks as the live page), recoloured for a dark ground
BINS = [0.05, 0.10, 0.20, 0.35, 0.50]
BIN_RGB = [(40, 40, 39), (66, 44, 41), (126, 31, 28), (176, 24, 27), (227, 6, 19), (255, 92, 72)]

# Fonts are looked up by file name in the usual Linux and macOS font folders.
# Linux: apt install fonts-montserrat fonts-inter fonts-jetbrains-mono
# macOS: install Montserrat, Inter and JetBrains Mono (e.g. Google Fonts) to ~/Library/Fonts
FONT_DIRS = ["/usr/share/fonts", "/usr/local/share/fonts", "~/.local/share/fonts", "~/.fonts",
             "~/Library/Fonts", "/Library/Fonts"]
FONT_FILES = {
    "title": "Montserrat-SemiBold.otf",
    "title_l": "Montserrat-Light.otf",
    "title_xl": "Montserrat-ExtraLight.otf",
    "body": "Inter-Light.otf",
    "body_r": "Inter-Regular.otf",
    "body_m": "Inter-Medium.otf",
    "mono": "JetBrainsMono-Regular.ttf",
}
_paths: dict = {}
_fonts: dict = {}


def font_path(name: str) -> str:
    if name not in _paths:
        for d in FONT_DIRS:
            hits = sorted(Path(d).expanduser().rglob(name)) if Path(d).expanduser().is_dir() else []
            if hits:
                _paths[name] = str(hits[0])
                break
        else:
            raise SystemExit(f"font {name} not found in {FONT_DIRS}; see the install note above FONT_DIRS")
    return _paths[name]


def font(key: str, size: int) -> ImageFont.FreeTypeFont:
    k = (key, size)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(font_path(FONT_FILES[key]), size)
    return _fonts[k]


# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def env(t, t0, t1, fin=0.6, fout=0.5):
    """Opacity: fade in from t0 over fin, fade out ending at t1 over fout."""
    if t < t0 or t > t1:
        return 0.0
    return min(ease((t - t0) / fin) if fin else 1.0, ease((t1 - t) / fout) if fout else 1.0)


def mix(c, a, bg=BG):
    return tuple(int(bg[i] + (c[i] - bg[i]) * a) for i in range(3))


# ------------------------------------------------------------------- text
def text(d: ImageDraw.ImageDraw, s, xy, f, c=INK, a=1.0, anchor="mm", track=0.0):
    """Draw text blended over BG with alpha `a`; `track` = letter-spacing in em."""
    if a <= 0.004 or not s:
        return
    fill = mix(c, a)
    if not track:
        d.text(xy, s, font=f, fill=fill, anchor=anchor)
        return
    sp = track * f.size
    widths = [f.getlength(ch) for ch in s]
    total = sum(widths) + sp * (len(s) - 1)
    x, y = xy
    x -= {"l": 0, "m": total / 2, "r": total}[anchor[0]]
    for ch, w in zip(s, widths):
        d.text((x, y), ch, font=f, fill=fill, anchor="l" + anchor[1])
        x += w + sp


def lines(d, rows, cx, cy, f, c=INK, a=1.0, lead=1.35, anchor="m", track=0.0):
    """Stack of centred (or left, anchor='l') lines around cy."""
    step = f.size * lead
    y0 = cy - step * (len(rows) - 1) / 2
    for i, r in enumerate(rows):
        text(d, r, (cx, y0 + i * step), f, c, a, anchor + "m", track)


def rule(d, x0, x1, y, a, c=INK3, w=1):
    if a > 0.004 and x1 > x0:
        d.line([(x0, y), (x1, y)], fill=mix(c, a), width=w)


# -------------------------------------------------------------------- data
def load_grid():
    if not GRID_JSON.exists():
        raise SystemExit(f"{GRID_JSON} missing: run `make atlas-grid` first")
    data = json.loads(GRID_JSON.read_text())
    groups = data["groups"]
    bands = []
    for s in data["sectors"]:
        sq = []
        for c in s["cells"]:
            sq += [groups[c["g"]]["beta"] or 0.0] * c["n"]
        sq.sort(reverse=True)
        bands.append({"key": s["key"], "label": s["label"], "workers_m": s["workers_m"],
                      "beta": s["beta"], "squares": sq})
    order = {"services": 0, "industry": 1, "agriculture": 2}
    bands.sort(key=lambda b: order[b["key"]])
    assert sum(len(b["squares"]) for b in bands) == data["total_squares"] == 463
    return bands


def load_event_study():
    rows = []
    pat = re.compile(r"^qcat::(\d{4})Q(\d):E\s+\S+\s+(-?[\d.]+)\s+([\d.]+)")
    for line in EVENT_TXT.read_text().splitlines():
        m = pat.match(line.strip())
        if m:
            rows.append((int(m[1]), int(m[2]), float(m[3]), float(m[4])))
    rows.append((2022, 4, 0.0, 0.0))  # omitted reference quarter
    rows.sort()
    return rows


def bin_rgb(beta):
    i = 0
    while i < len(BINS) and beta >= BINS[i]:
        i += 1
    return BIN_RGB[i]


# ================================================================ timeline
# (start, end, name). Scene functions receive global t.
T = {
    "cold": (0.0, 7.0), "title": (7.0, 13.5),
    "signal": (13.5, 28.0), "fear": (28.0, 41.0), "build": (41.0, 59.0),
    "atlas": (59.0, 81.0), "money": (81.0, 94.5), "who": (94.5, 110.0),
    "canary": (110.0, 125.0), "mirror": (125.0, 137.5), "coda": (137.5, 146.0),
    "end": (146.0, 156.0),
}
DURATION = T["end"][1]
IMAX = [(59.2, 80.4), (116.0, 121.2)]  # full-frame windows (bars retract)


def bars(t):
    """Letterbox bar height at t (retracts over 0.9 s inside IMAX windows)."""
    k = 0.0
    for a, b in IMAX:
        k = max(k, min(ease((t - a) / 0.9), ease((b - t) / 0.9)))
    return BAR * (1 - k)


def intertitle(d, t, t0, num, title, src):
    a = env(t, t0, t0 + 2.6, 0.5, 0.45)
    if a <= 0:
        return
    text(d, num, (W / 2, H / 2 - 62), font("mono", 24), RED, a, track=0.3)
    text(d, title, (W / 2, H / 2), font("title", 50), INK, a, track=0.42)
    g = ease_out((t - t0 - 0.2) / 1.4)
    rule(d, W / 2 - 220 * g, W / 2 + 220 * g, H / 2 + 50, a)
    text(d, src, (W / 2, H / 2 + 88), font("mono", 18), INK2, a, track=0.14)


def caption(d, t, t0, t1, rows, y=H / 2 + 150, size=34, c=INK2):
    lines(d, rows, W / 2, y, font("body", size), c, env(t, t0, t1, 0.6, 0.45))


def source(d, t, t0, t1, s):
    text(d, s, (W / 2, H - BAR - 40), font("mono", 17), INK2, env(t, t0, t1, 0.8, 0.4) * 0.8,
         track=0.08)


def fmt_int(n):
    return f"{int(round(n)):,}"


# ------------------------------------------------------------------ scenes
def s_cold(d, t, ctx):
    a = env(t, 1.0, 6.5, 0.3, 0.12)
    k = ease_out((t - 1.0) / 2.2)
    text(d, fmt_int(463_000_000 * k), (W / 2, H / 2 - 20), font("title_xl", 150), INK, a, track=0.08)
    text(d, "WORKERS.", (W / 2, H / 2 + 105), font("title", 28), INK2, env(t, 3.4, 6.5, 0.5, 0.12),
         track=0.6)
    text(d, "ONE QUESTION.", (W / 2, H / 2 + 160), font("title", 28), RED, env(t, 4.6, 6.5, 0.4, 0.12),
         track=0.6)


def s_title(d, t, ctx):
    a = env(t, 7.4, 13.2, 1.0, 0.6)
    text(d, "WHERE DOES AI", (W / 2, H / 2 - 58), font("title", 76), INK, a, track=0.32)
    text(d, "ACTUALLY LAND IN INDIA?", (W / 2, H / 2 + 38), font("title", 76), INK, a, track=0.32)
    b = env(t, 8.8, 13.2, 0.8, 0.6)
    text(d, "AN ATLAS OF 463 MILLION WORKERS  ·  SURYADIP GHOSHAL", (W / 2, H / 2 + 138),
         font("mono", 20), INK2, b, track=0.22)


def big_number(d, t, t0, t1, s, c, y=H / 2 - 40, size=190):
    a = env(t, t0, t1, 0.35, 0.4)
    text(d, s, (W / 2, y), font("title_l", size), c, a, track=0.02)


def s_signal(d, t, ctx):
    t0 = T["signal"][0]
    intertitle(d, t, t0, "I", "THE SIGNAL", "ANTHROPIC ECONOMIC INDEX  ·  INDIA")
    big_number(d, t, t0 + 2.9, t0 + 7.4, "45%", RED)
    caption(d, t, t0 + 3.4, t0 + 7.4, ["of Indian work with Claude maps to software occupations.",
                                       "The highest share of any country."])
    big_number(d, t, t0 + 7.6, t0 + 11.3, "0.27×", INK)
    caption(d, t, t0 + 8.0, t0 + 11.3, ["India's usage per working-age adult, against its population weight.",
                                        "Among the lowest measured."])
    lines(d, ["A few million coders met AI early."], W / 2, H / 2 - 40, font("body", 46), INK,
          env(t, t0 + 11.5, t0 + 14.3, 0.5, 0.4))
    lines(d, ["450 million other workers have barely met it."], W / 2, H / 2 + 40, font("body", 46),
          RED, env(t, t0 + 12.4, t0 + 14.3, 0.5, 0.4))
    source(d, t, t0 + 2.9, t0 + 11.3, "SOURCE: ANTHROPIC ECONOMIC INDEX, INDIA BRIEF (FEB 2026)")


def s_fear(d, t, ctx):
    t0 = T["fear"][0]
    intertitle(d, t, t0, "II", "THE IMPORTED FEAR", "EVERY ESTIMATE SO FAR WAS BUILT ELSEWHERE")
    a = env(t, t0 + 2.9, t0 + 6.9, 0.6, 0.4)
    lines(d, ["“AI could wipe out half of all", "entry-level white-collar jobs.”"],
          W / 2, H / 2 - 40, font("title_l", 58), INK, a, lead=1.3)
    text(d, "DARIO AMODEI  ·  AXIOS  ·  MAY 2025", (W / 2, H / 2 + 90), font("mono", 20), INK2,
         env(t, t0 + 3.5, t0 + 6.9, 0.6, 0.4), track=0.2)
    # -13% -> -19%
    a2 = env(t, t0 + 7.1, t0 + 10.4, 0.4, 0.4)
    text(d, "−13%", (W / 2 - 230, H / 2 - 40), font("title_l", 150), INK2, a2)
    text(d, "→", (W / 2, H / 2 - 40), font("body", 90), INK3, env(t, t0 + 7.8, t0 + 10.4, 0.3, 0.4))
    text(d, "−19%", (W / 2 + 240, H / 2 - 40), font("title_l", 150), RED, env(t, t0 + 8.2, t0 + 10.4, 0.3, 0.4))
    caption(d, t, t0 + 7.5, t0 + 10.4, ["US workers aged 22 to 25 in the most exposed jobs, against their peers.",
                                        "Stanford payroll study, to its August 2026 update."], y=H / 2 + 120)
    a3 = env(t, t0 + 10.6, t0 + 13.0, 0.4, 0.35)
    text(d, "US OCCUPATIONS.  US TASKS.", (W / 2, H / 2 - 40), font("title", 44), INK, a3, track=0.3)
    lines(d, ["Carried to India through a crosswalk that drops content on the way."], W / 2, H / 2 + 40,
          font("body", 34), INK2, env(t, t0 + 11.1, t0 + 13.0, 0.4, 0.35))


VERBS = ["examining records", "preparing documents", "operating equipment", "teaching",
         "selling", "repairing", "driving", "supervising"]


def s_build(d, t, ctx):
    t0 = T["build"][0]
    intertitle(d, t, t0, "III", "THE BUILD", "INDIA'S OWN OCCUPATIONS  ·  INDIA'S OWN TASKS")
    steps = [
        ("18,622", "TASK STATEMENTS", "NCO-2015"),
        ("E0 · E1 · E2", "ONE RUBRIC", "EVERY TASK"),
        ("122", "OCCUPATION GROUPS", "α · β · ζ"),
        ("463M", "WORKERS", "PLFS 2023-24"),
    ]
    s0, sd = t0 + 2.9, 3.7
    a_all = env(t, s0, T["build"][1] - 0.1, 0.5, 0.5)
    if a_all <= 0:
        return
    xs = [W / 2 - 600 + i * 400 for i in range(4)]
    ytrack = H / 2 + 175
    cur = int(clamp((t - s0) // sd, 0, 3))
    # track line + nodes
    prog = clamp((t - s0) / (4 * sd))
    rule(d, xs[0], xs[3], ytrack, a_all * 0.8, INK3, 2)
    rule(d, xs[0], xs[0] + (xs[3] - xs[0]) * ease(prog * 1.1), ytrack, a_all, RED, 2)
    for i, x in enumerate(xs):
        on = t >= s0 + i * sd
        r = 9 if i == cur else 6
        col = mix(RED if on else INK3, a_all)
        d.ellipse([x - r, ytrack - r, x + r, ytrack + r], fill=col if on else None, outline=col, width=2)
        text(d, steps[i][1], (x, ytrack + 42), font("mono", 17), INK if i == cur else INK2,
             a_all * (1 if on else 0.5), track=0.16)
        text(d, steps[i][2], (x, ytrack + 70), font("mono", 15), INK3, a_all * (1 if on else 0.5), track=0.12)
    # stage above the track
    ls = t - (s0 + cur * sd)
    a = a_all * min(ease(ls / 0.45), 1.0 if cur == 3 else ease((sd - ls) / 0.35))
    cy = H / 2 - 120
    if cur == 0:
        n = 18622 * ease_out(ls / 1.8)
        text(d, fmt_int(n), (W / 2, cy - 20), font("title_l", 130), INK, a)
        v = VERBS[int((ls * 3.2)) % len(VERBS)]
        text(d, v, (W / 2, cy + 90), font("body", 36), RED, a)
        text(d, "short descriptions of work, parsed from India's occupation volumes", (W / 2, cy + 150),
             font("body", 24), INK2, a)
    elif cur == 1:
        lines(d, ["Would access to an LLM cut the time this task takes", "by at least half, at equal quality?"],
              W / 2, cy - 40, font("title_l", 44), INK, a, lead=1.35)
        labels = [("E0", "not exposed"), ("E1", "chat interface alone"), ("E2", "needs extra tooling")]
        for j, (k, v) in enumerate(labels):
            x = W / 2 + (j - 1) * 380
            aj = a * ease((ls - 0.8 - j * 0.35) / 0.4)
            text(d, k, (x, cy + 90), font("title", 40), RED if j else INK2, aj)
            text(d, v, (x, cy + 135), font("body", 24), INK2, aj)
    elif cur == 2:
        text(d, "122", (W / 2, cy - 50), font("title_l", 130), INK, a)
        labels = [("α", "share of tasks E1"), ("β", "E1 + ½ E2  ·  headline"), ("ζ", "E1 + E2  ·  upper bound")]
        for j, (k, v) in enumerate(labels):
            x = W / 2 + (j - 1) * 420
            aj = a * ease((ls - 0.5 - j * 0.35) / 0.4)
            text(d, k, (x, cy + 70), font("body", 56), RED if j == 1 else INK, aj)
            text(d, v, (x, cy + 125), font("body", 24), INK2, aj)
    else:
        n = 463 * ease_out(ls / 1.6)
        text(d, f"{n:,.0f} MILLION", (W / 2, cy - 20), font("title_l", 110), INK, a, track=0.04)
        text(d, "principal-status workers, weighted from PLFS 2023-24 worker records", (W / 2, cy + 80),
             font("body", 26), INK2, a)


def grid_layout(bands):
    cols, pitch, gap = 30, 33, 4
    x0, y = 150, 150
    lay, heads = [], []
    for b in bands:
        heads.append((b, y))
        y += 40
        for i, beta in enumerate(b["squares"]):
            r, c = divmod(i, cols)
            lay.append((x0 + c * pitch, y + r * pitch, pitch - gap, beta, b["key"]))
        y += math.ceil(len(b["squares"]) / cols) * pitch + 20
    return lay, heads


def s_atlas(d, t, ctx):
    t0, t1 = T["atlas"]
    lay, heads = ctx["grid"]
    ga = env(t, t0 + 0.4, t1 - 0.3, 0.3, 0.8)
    if ga <= 0:
        return
    hi_band = None
    if t0 + 11.2 <= t < t0 + 13.4:
        hi_band = "agriculture"
    dim_all = 1 - 0.75 * env(t, t0 + 15.8, t1, 0.8, 0.3)
    rnd = ctx["jitter"]
    for i, (x, y, s, beta, key) in enumerate(lay):
        start = t0 + 0.8 + 3.6 * (i / len(lay)) + rnd[i]
        k = ease_out((t - start) / 0.5)
        if k <= 0:
            continue
        a = ga * k * dim_all
        if hi_band and key != hi_band:
            a *= 0.3
        dy = (1 - k) * -18
        d.rectangle([x, y + dy, x + s, y + dy + s], fill=mix(bin_rgb(beta), a))
    for b, y in heads:
        ha = ga * env(t, t0 + 1.2, t1, 0.8, 0.8) * dim_all
        if hi_band and b["key"] != hi_band:
            ha *= 0.3
        text(d, b["label"].upper(), (150, y + 14), font("mono", 17), INK, ha, "lm", track=0.2)
        text(d, f"{b['workers_m']:.0f}M  ·  β {b['beta']:.3f}", (150 + 30 * 33 - 4, y + 14),
             font("mono", 17), INK2, ha, "rm", track=0.06)
    # legend
    la = ga * env(t, t0 + 4.4, t1, 0.8, 0.8) * dim_all
    lx, ly = 150, H - 120
    text(d, "ONE SQUARE = ONE MILLION WORKERS  ·  COLOUR = β EXPOSURE", (lx, ly - 34), font("mono", 16),
         INK2, la, "lm", track=0.14)
    edges = ["0", ".05", ".10", ".20", ".35", ".50+"]
    for j, c in enumerate(BIN_RGB):
        d.rectangle([lx + j * 80, ly, lx + j * 80 + 76, ly + 12], fill=mix(c, la))
        text(d, edges[j], (lx + j * 80, ly + 30), font("mono", 15), INK3, la, "lm")
    # right panel
    rx = 1270
    a1 = env(t, t0 + 5.4, t0 + 10.6, 0.6, 0.4)
    text(d, "5 in 6", (rx, 380), font("title_l", 120), INK, a1, "lm")
    lines(d, ["tasks came back marked", "no exposure."], rx, 505, font("body", 34), INK2, a1, anchor="l")
    tb = [(15498, INK3), (1946, RED), (1150, (126, 31, 28))]
    x = rx
    for n, c in tb:
        w = 520 * n / 18594 * ease_out((t - t0 - 6.0) / 1.2)
        d.rectangle([x, 600, x + w, 624], fill=mix(c, a1))
        x += w
    text(d, "E0 15,498   E1 1,946   E2 1,150", (rx, 655), font("mono", 17), INK2, a1, "lm", track=0.04)
    rows = [("AGRICULTURE", "194M", "0.06", t0 + 11.0), ("CONSTRUCTION", "60M", "0.03", t0 + 12.0),
            ("IT & COMMUNICATION", "7M", "0.54", t0 + 13.0)]
    for j, (lab, m, b, ts) in enumerate(rows):
        a = env(t, ts, t0 + 15.6, 0.5, 0.4)
        y = 420 + j * 120
        text(d, lab, (rx, y - 26), font("mono", 18), INK2, a, "lm", track=0.2)
        text(d, m, (rx, y + 22), font("title_l", 58), INK, a, "lm")
        text(d, b, (rx + 360, y + 22), font("title_l", 58), RED if j == 2 else INK, a, "lm")
    text(d, "WORKERS", (rx, 330), font("mono", 14), INK3, env(t, t0 + 11.0, t0 + 15.6, 0.5, 0.4), "lm", track=0.2)
    text(d, "β", (rx + 360, 330), font("mono", 16), INK3, env(t, t0 + 11.0, t0 + 15.6, 0.5, 0.4), "lm")
    a3 = env(t, t0 + 16.2, t1 - 0.3, 0.4, 0.6)
    text(d, "0.086", (1520, H / 2 - 60), font("title_xl", 190), INK, a3)
    text(d, "ECONOMY-WIDE MEAN EXPOSURE", (1520, H / 2 + 80), font("mono", 20), INK2, a3, track=0.24)
    text(d, "For most of India, it is not close.", (1520, H / 2 + 150), font("body", 36), RED,
         env(t, t0 + 17.6, t1 - 0.3, 0.5, 0.6))


def hbar(d, x, y, w, h, frac, c, a, maxw):
    d.rectangle([x, y, x + maxw, y + h], fill=mix(INK3, a * 0.35))
    d.rectangle([x, y, x + maxw * frac, y + h], fill=mix(c, a))


def s_money(d, t, ctx):
    t0 = T["money"][0]
    intertitle(d, t, t0, "IV", "FOLLOW THE MONEY", "OCCUPATIONS SCORING β ≥ 0.5")
    a = env(t, t0 + 2.9, t0 + 7.4, 0.5, 0.4)
    g = ease_out((t - t0 - 3.3) / 1.6)
    x, mw = W / 2 - 380, 760
    text(d, "SHARE OF WORKERS", (x, H / 2 - 110), font("mono", 18), INK2, a, "lm", track=0.2)
    hbar(d, x, H / 2 - 85, 0, 30, 0.019 / 0.08 * g, INK, a, mw)
    text(d, f"{1.9 * g:.1f}%", (x + mw + 30, H / 2 - 70), font("title_l", 48), INK, a, "lm")
    text(d, "SHARE OF THE WAGE BILL", (x, H / 2 + 10), font("mono", 18), INK2, a, "lm", track=0.2)
    hbar(d, x, H / 2 + 35, 0, 30, 0.071 / 0.08 * g, RED, a, mw)
    text(d, f"{7.1 * g:.1f}%", (x + mw + 30, H / 2 + 50), font("title_l", 48), RED, a, "lm")
    a2 = env(t, t0 + 7.6, t0 + 10.6, 0.4, 0.4)
    text(d, "0.086", (W / 2 - 250, H / 2 - 40), font("title_l", 130), INK2, a2)
    text(d, "→", (W / 2, H / 2 - 40), font("body", 80), INK3, a2)
    text(d, "0.155", (W / 2 + 250, H / 2 - 40), font("title_l", 130), RED, env(t, t0 + 8.1, t0 + 10.6, 0.3, 0.4))
    caption(d, t, t0 + 8.1, t0 + 10.6, ["Weight exposure by pay instead of headcount and it nearly doubles.",
                                        "In IT, three quarters of the paycheque sits in exposed jobs."],
            y=H / 2 + 110)
    a3 = env(t, t0 + 10.8, T["money"][1] - 0.1, 0.4, 0.4)
    text(d, "AN INCOME STORY", (W / 2, H / 2 - 40), font("title", 54), INK, a3, track=0.3)
    text(d, "BEFORE IT IS A JOBS-COUNT STORY.", (W / 2, H / 2 + 40), font("title", 34), INK2, a3, track=0.3)


def pair(d, x, label, w_val, m_val, a, g, red_w):
    base = H / 2 + 150
    text(d, label, (x - 5, base + 75), font("mono", 18), INK2, a, track=0.24)
    for j, (lab, v) in enumerate([("WOMEN", w_val), ("MEN", m_val)]):
        bx = x - 110 + j * 150
        hgt = 1250 * v * g
        c = RED if (j == 0 and red_w) else INK
        d.rectangle([bx, base - hgt, bx + 70, base], fill=mix(c if j == 0 else INK2, a))
        text(d, f"{v:.2f}", (bx + 35, base - hgt - 30), font("title_l", 34), c if j == 0 else INK2, a * g)
        text(d, lab, (bx + 35, base + 30), font("mono", 16), INK2, a, track=0.2)


def s_who(d, t, ctx):
    t0 = T["who"][0]
    intertitle(d, t, t0, "V", "WHO, EXACTLY", "PLFS 2023-24  ·  MEAN β EXPOSURE")
    a = env(t, t0 + 2.9, t0 + 9.0, 0.5, 0.4)
    pair(d, W / 2 - 330, "ALL WORKERS", 0.07, 0.09, a, ease_out((t - t0 - 3.1) / 1.2), False)
    a_org = env(t, t0 + 4.6, t0 + 9.0, 0.5, 0.4)
    pair(d, W / 2 + 330, "ORGANISED SECTOR", 0.26, 0.25, a_org, ease_out((t - t0 - 4.8) / 1.2), True)
    text(d, "THE SIGN REVERSES.", (W / 2, H - BAR - 90), font("title", 30), RED,
         env(t, t0 + 6.2, t0 + 9.0, 0.4, 0.4), track=0.34)
    # entry rung
    a2 = env(t, t0 + 9.2, T["who"][1] - 0.1, 0.4, 0.4)
    text(d, "WHITE-COLLAR WORKERS IN HIGH-EXPOSURE OCCUPATIONS", (W / 2, H / 2 - 190), font("mono", 18),
         INK2, a2, track=0.2)
    text(d, "22%", (W / 2 - 260, H / 2 - 40), font("title_l", 170), RED, a2)
    text(d, "AGED 18 TO 29", (W / 2 - 260, H / 2 + 80), font("mono", 18), INK, a2, track=0.2)
    text(d, "11%", (W / 2 + 260, H / 2 - 40), font("title_l", 170), INK2, a2)
    text(d, "THEIR SENIORS", (W / 2 + 260, H / 2 + 80), font("mono", 18), INK2, a2, track=0.2)
    caption(d, t, t0 + 10.6, T["who"][1] - 0.1,
            ["About 3.5 million young workers hold those rungs.",
             "Indian IT hires at the bottom of a pyramid. The bottom is where the model lands first."],
            y=H / 2 + 170, size=30)


def s_canary(d, t, ctx):
    t0, t1 = T["canary"]
    intertitle(d, t, t0, "VI", "THE CANARY", "EPFO PAYROLL  ·  88 MONTHS  ·  BEFORE AND AFTER CHATGPT")
    rows = ctx["event"]
    a = env(t, t0 + 2.9, t0 + 11.1, 0.6, 0.35)
    if a > 0:
        x0, x1, yc, sc = 260, W - 260, H / 2 + 20, 110  # sc = px per unit
        n = len(rows)
        xs = [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]
        lim = 2.0
        rule(d, x0 - 30, x1 + 30, yc, a, INK3, 1)
        ref = [i for i, r in enumerate(rows) if (r[0], r[1]) == (2022, 4)][0]
        xr = (xs[ref] + xs[ref + 1]) / 2
        d.line([(xr, yc - lim * sc - 20), (xr, yc + lim * sc + 20)], fill=mix(RED, a * 0.8), width=1)
        text(d, "CHATGPT  ·  NOV 2022", (xr + 14, yc - lim * sc - 10), font("mono", 16), RED, a, "lm", track=0.16)
        shown = (t - t0 - 3.3) / 4.4 * n
        for i, (yr, q, b, se) in enumerate(rows):
            if i > shown:
                break
            post = (yr, q) > (2022, 4)
            c = RED if post else INK2
            lo, hi = b - 1.96 * se, b + 1.96 * se
            ylo = yc - clamp(hi, -lim, lim) * sc
            yhi = yc - clamp(lo, -lim, lim) * sc
            d.line([(xs[i], ylo), (xs[i], yhi)], fill=mix(c, a * 0.55), width=2)
            for yy, v in ((ylo, hi), (yhi, lo)):
                if abs(v) > lim:  # clipped whisker marker
                    d.line([(xs[i] - 5, yy), (xs[i] + 5, yy)], fill=mix(c, a * 0.55), width=2)
            yb = yc - clamp(b, -lim, lim) * sc
            if abs(b) > lim:  # clipped estimate: open down-pointing triangle
                d.polygon([(xs[i] - 7, yb - 5), (xs[i] + 7, yb - 5), (xs[i], yb + 8)], outline=mix(c, a))
            else:
                d.ellipse([xs[i] - 6, yb - 6, xs[i] + 6, yb + 6], fill=mix(c, a))
            if q == 1 and yr in (2021, 2023, 2025):
                text(d, str(yr), (xs[i], yc + lim * sc + 45), font("mono", 16), INK3, a)
        text(d, "YOUNG-WORKER NET PAYROLL ADDITIONS × EXPOSURE  ·  QUARTERLY EVENT STUDY  ·  95% CI  ·  2020 COVID QUARTERS CLIPPED",
             (W / 2, yc + lim * sc + 90), font("mono", 16), INK2, a, track=0.1)
        lines(d, ["The point estimates lean negative.", "None is statistically significant."],
              W / 2, 150, font("body", 32), INK, env(t, t0 + 8.0, t0 + 11.1, 0.5, 0.35))
    # the clock stops at ~t0+11.4; a beat of black, then the line
    a3 = env(t, t0 + 12.2, t1 - 0.1, 0.9, 0.5)
    text(d, "THE CANARY HAS NOT SUNG.", (W / 2, H / 2 - 20), font("title", 52), INK, a3, track=0.34)
    text(d, "I would rather report that than dress it up.", (W / 2, H / 2 + 60), font("body", 30), INK2,
         env(t, t0 + 13.2, t1 - 0.1, 0.6, 0.5))


def s_mirror(d, t, ctx):
    t0, t1 = T["mirror"]
    intertitle(d, t, t0, "VII", "THE MIRROR", "THE US O*NET CROSSWALK  vs  INDIA'S OWN TASK CONTENT")
    a = env(t, t0 + 2.9, t0 + 7.2, 0.5, 0.4)
    text(d, "O*NET CROSSWALK", (W / 2 - 330, H / 2 - 150), font("mono", 18), INK2, a, track=0.2)
    text(d, "0.204", (W / 2 - 330, H / 2 - 40), font("title_l", 140), INK2, a)
    text(d, "NCO-2015 TASKS", (W / 2 + 330, H / 2 - 150), font("mono", 18), INK2, a, track=0.2)
    text(d, "0.086", (W / 2 + 330, H / 2 - 40), font("title_l", 140), INK, a)
    k = env(t, t0 + 4.2, t0 + 7.2, 0.4, 0.4)
    text(d, "2.4×", (W / 2, H / 2 + 110), font("title", 70), RED, k, track=0.06)
    text(d, "82 OF 122 GROUPS  ·  191 MILLION WORKERS  ·  DIVERGE SUBSTANTIALLY", (W / 2, H / 2 + 185),
         font("mono", 17), INK2, k, track=0.14)
    a2 = env(t, t0 + 7.4, t1 - 0.1, 0.5, 0.4)
    text(d, "BANK TELLER", (W / 2, H / 2 - 190), font("title", 30), INK, a2, track=0.4)
    rule(d, W / 2, W / 2, H / 2 - 110, a2)
    d.line([(W / 2, H / 2 - 120), (W / 2, H / 2 + 80)], fill=mix(INK3, a2), width=1)
    text(d, "INDIA  ·  NCO-2015", (W / 2 - 60, H / 2 - 100), font("mono", 17), INK2, a2, "rm", track=0.2)
    lines(d, ["ledger books", "specimen signatures", "cash at a counter"], W / 2 - 60, H / 2 - 10,
          font("body", 34), INK, a2, anchor="r")
    text(d, "US  ·  O*NET", (W / 2 + 60, H / 2 - 100), font("mono", 17), INK2, a2, "lm", track=0.2)
    lines(d, ["transaction software"], W / 2 + 60, H / 2 - 10, font("body", 34), INK, a2, anchor="l")
    text(d, "SAME LABEL.  DIFFERENT JOB.", (W / 2, H / 2 + 160), font("title", 36), RED,
         env(t, t0 + 9.0, t1 - 0.1, 0.4, 0.4), track=0.3)


def s_coda(d, t, ctx):
    t0, t1 = T["coda"]
    a = env(t, t0 + 0.3, t0 + 4.4, 0.7, 0.4)
    lines(d, ["Exposure measures task overlap today.", "It forecasts nothing about employment tomorrow."],
          W / 2, H / 2, font("title_l", 46), INK, a, lead=1.5)
    a2 = env(t, t0 + 4.7, t1 - 0.1, 0.7, 0.6)
    text(d, "ADOPTION IS A CHOICE.", (W / 2, H / 2 - 40), font("title", 52), INK, a2, track=0.34)
    text(d, "CHOICES HAVE OWNERS.", (W / 2, H / 2 + 50), font("title", 52), RED,
         env(t, t0 + 5.6, t1 - 0.1, 0.7, 0.6), track=0.34)


def s_end(d, t, ctx):
    t0, t1 = T["end"]
    a = env(t, t0 + 0.4, t1, 1.0, 1.2)
    text(d, "EVERY SQUARE OPENS TO ITS TASKS.", (W / 2, H / 2 - 150), font("title", 34), INK, a, track=0.34)
    links = [("THE ATLAS", "suryaghoshal5.github.io/ai-atlas"),
             ("THE ESSAY", "suryadipghoshal.substack.com/p/463-million-workers-one-question"),
             ("THE CODE", "github.com/suryaghoshal5/ai-atlas")]
    for j, (k, v) in enumerate(links):
        aj = env(t, t0 + 1.0 + j * 0.4, t1, 0.7, 1.2)
        y = H / 2 - 40 + j * 62
        text(d, k, (W / 2 - 440, y), font("mono", 18), RED, aj, "lm", track=0.24)
        text(d, v, (W / 2 - 250, y), font("body_r", 30), INK, aj, "lm")
    ap = env(t, t0 + 2.4, t1, 0.8, 1.2)
    text(d, "PRELIMINARY  ·  TASK SCORES ARE LLM-ONLY; HUMAN VALIDATION PENDING  ·  PLFS 2023-24 × NCO-2015",
         (W / 2, H / 2 + 210), font("mono", 16), INK2, ap, track=0.12)
    text(d, "SURYADIP GHOSHAL", (W / 2, H / 2 + 260), font("title", 22), INK2, ap, track=0.5)


SCENES = [(T[k], f) for k, f in [
    ("cold", s_cold), ("title", s_title), ("signal", s_signal), ("fear", s_fear), ("build", s_build),
    ("atlas", s_atlas), ("money", s_money), ("who", s_who), ("canary", s_canary), ("mirror", s_mirror),
    ("coda", s_coda), ("end", s_end)]]

# --------------------------------------------------------------- post / ctx
_CTX: dict = {}


def init_ctx():
    rnd = random.Random(run_seed())
    bands = load_grid()
    lay, heads = grid_layout(bands)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    rng = np.random.default_rng(run_seed())
    _CTX.update(
        bands=bands, grid=(lay, heads), jitter=[rnd.uniform(0, 0.5) for _ in lay],
        event=load_event_study(),
        vignette=(1 - 0.38 * np.clip(r - 0.35, 0, None) ** 1.6)[..., None].astype(np.float32),
        grain=[rng.normal(0, 5.0, (H, W, 1)).astype(np.float32) for _ in range(8)],
    )


def push(t):
    """Slow camera push within each scene (1.0 -> 1.025)."""
    for (a, b), _ in SCENES:
        if a <= t < b:
            return 1.0 + 0.025 * (t - a) / (b - a)
    return 1.0


def render(i: int) -> bytes:
    t = i / FPS
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for (a, b), fn in SCENES:
        if a - 0.05 <= t <= b + 0.05:
            fn(d, t, _CTX)
    s = push(t)
    if s > 1.0005:
        big = img.resize((round(W * s), round(H * s)), Image.BILINEAR)
        ox, oy = (big.width - W) // 2, (big.height - H) // 2
        img = big.crop((ox, oy, ox + W, oy + H))
    arr = np.asarray(img, dtype=np.float32)
    arr = arr * _CTX["vignette"] + _CTX["grain"][i % 8]
    bh = int(round(bars(t)))
    if bh:
        arr[:bh] = 0
        arr[H - bh:] = 0
    return np.clip(arr, 0, 255).astype(np.uint8).tobytes()


# ==================================================================== score
def lp(x, fc):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, fc, "low", fs=SR, output="sos"), x)


def hp(x, fc):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, fc, "high", fs=SR, output="sos"), x)


CLOCK_STOP = T["canary"][0] + 11.4

# Score cue sheet: every sound event keyed to picture time. The short cut
# (insights.film_short) passes its own sheet to the same synthesiser.
CUES = {
    "duration": DURATION,
    "rate_pts": [(0, 1.0), (7, 1.0), (59, 1.5), (81, 1.5), (110, 2.0), (121.3, 3.2)],
    "clock_stop": CLOCK_STOP,
    "tick_ramp": (59, 119),
    "watch2": (T["mirror"][0] + 0.5, T["end"][0]),     # quiet second watch
    "drone_mute": (CLOCK_STOP, T["mirror"][0]),       # silence after the clock stops
    "shepard": [(T["build"][0] + 2.5, T["build"][1], 0.028), (T["canary"][0] + 2.5, CLOCK_STOP, 0.04)],
    "braams": [(1.0, 0.55), (7.4, 0.35), (T["atlas"][0] + 0.8, 0.7), (T["atlas"][0] + 16.2, 0.6),
               (T["canary"][0] + 12.2, 0.4), (T["mirror"][0] + 4.2, 0.5), (T["coda"][0] + 4.7, 0.45)],
    "end_note": T["end"][0] + 0.4,
}


def score(cues: dict = CUES) -> np.ndarray:
    n = int(cues["duration"] * SR)
    tt = np.arange(n) / SR
    pts = cues["rate_pts"]

    def tick_rate(t):
        for (a, ra), (b, rb) in zip(pts, pts[1:]):
            if a <= t < b:
                return ra + (rb - ra) * (t - a) / (b - a)
        return 0.0

    clock_stop = cues["clock_stop"]
    ra0, ra1 = cues["tick_ramp"]  # window over which tick level rises
    rng = np.random.default_rng(run_seed())
    out = np.zeros((n, 2))

    # --- pocket-watch ticks, accelerating, stopping dead before the canary line
    ticks = np.zeros(n)
    click_t = np.arange(int(0.03 * SR)) / SR
    tick = (np.sin(2 * np.pi * 3100 * click_t) * np.exp(-click_t / 0.004)
            + 0.6 * hp(rng.normal(0, 1, click_t.size), 2500) * np.exp(-click_t / 0.002))
    tock = (np.sin(2 * np.pi * 2300 * click_t) * np.exp(-click_t / 0.005)
            + 0.5 * hp(rng.normal(0, 1, click_t.size), 2000) * np.exp(-click_t / 0.002))
    t, k = 0.6, 0
    while t < clock_stop:
        r = tick_rate(t)
        if r <= 0:
            break
        i = int(t * SR)
        g = 0.22 + 0.12 * clamp((t - ra0) / (ra1 - ra0))
        seg = (tick if k % 2 == 0 else tock) * g
        ticks[i:i + seg.size] += seg[: n - i]
        t += 1.0 / r
        k += 1
    # a slow, quiet resumption under the mirror/coda, like a second watch
    t, t_end = cues["watch2"]
    while t < t_end:
        i = int(t * SR)
        seg = (tick if k % 2 == 0 else tock) * 0.08
        ticks[i:i + seg.size] += seg[: n - i]
        t += 1.0
        k += 1
    out += ticks[:, None] * np.array([0.9, 1.0])

    # --- low drone (D1 / A1 / D2) with slow swell, silent in the canary beat
    drone = (np.sin(2 * np.pi * 36.71 * tt) + 0.7 * np.sin(2 * np.pi * 55.0 * tt + 0.3)
             + 0.35 * np.sin(2 * np.pi * 73.42 * tt + 1.1))
    drone += 0.8 * lp(rng.normal(0, 1, n), 160)
    denv = 0.08 + 0.05 * np.sin(2 * np.pi * tt / 23.0) ** 2
    denv = np.where((tt > cues["drone_mute"][0]) & (tt < cues["drone_mute"][1]), 0.0, denv)
    denv = np.where(tt < 0.6, 0.0, denv)
    denv = np.convolve(denv, np.ones(SR // 5) / (SR // 5), mode="same")
    out += (drone * denv)[:, None] * np.array([1.0, 0.95])

    # --- Shepard tone: endless rise under the build and the canary
    def shepard(a, b, gain):
        m = (tt >= a) & (tt < b)
        ts = tt[m] - a
        sig = np.zeros(ts.size)
        rise = ts / 14.0  # octaves climbed
        for o in range(7):
            pos = (o + rise) % 7  # octave position 0..7
            f = 40.0 * 2 ** pos
            amp = np.exp(-0.5 * ((pos - 3.5) / 1.3) ** 2)
            ph = 2 * np.pi * np.cumsum(f) / SR
            sig += amp * np.sin(ph)
        e = np.minimum(1, ts / 2.0) * gain
        sig *= e
        tail = int(0.02 * SR)
        sig[-tail:] *= np.linspace(1, 0, tail)  # hard cut, no click
        out[m] += sig[:, None] * np.array([1.0, 1.0])

    for a, b, g in cues["shepard"]:
        shepard(a, b, g)

    # --- braams on the reveals
    def braam(at, gain=0.5, dur=5.0):
        i0 = int(at * SR)
        m = min(int(dur * SR), n - i0)
        ts = np.arange(m) / SR
        fc = 120 + 900 * np.exp(-ts / 0.9) * (1 - np.exp(-ts / 0.08))
        sig = np.zeros(m)
        for f0 in (43.65, 65.41, 87.31):
            for h in range(1, 28):
                fh = f0 * h
                g = 1.0 / (1 + (fh / fc) ** 4)
                sig += g / h * np.sin(2 * np.pi * fh * ts * (1 + 0.002 * (h % 3)))
        e = (1 - np.exp(-ts / 0.06)) * np.exp(-ts / 1.6)
        sig *= e * gain / 6
        out[i0:i0 + m] += sig[:, None] * np.array([1.0, 0.97])

    for at, g in cues["braams"]:
        braam(at, g)

    # --- closing low note
    i0 = int(cues["end_note"] * SR)
    ts = np.arange(n - i0) / SR
    note = sum(np.sin(2 * np.pi * 73.42 * h * ts) / h ** 1.5 for h in range(1, 8))
    out[i0:] += (note * np.exp(-ts / 2.8) * (1 - np.exp(-ts / 0.01)) * 0.18)[:, None]

    # --- room: short convolution reverb
    from scipy.signal import fftconvolve
    ir_t = np.arange(int(1.6 * SR)) / SR
    for ch in range(2):
        ir = rng.normal(0, 1, ir_t.size) * np.exp(-ir_t / 0.35)
        ir[0] = 0
        wet = fftconvolve(out[:, ch], ir)[:n]
        out[:, ch] = out[:, ch] + 0.012 * wet
    fade = int(1.5 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return out / (np.abs(out).max() + 1e-9) * 0.89


def write_wav(path: Path, x: np.ndarray):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


# ===================================================================== main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", help="comma-separated seconds; write PNGs only")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.stills:
        init_ctx()
        for s in args.stills.split(","):
            i = int(float(s) * FPS)
            Image.frombytes("RGB", (W, H), render(i)).save(out / f"still_{float(s):06.1f}.png")
        return

    wav = out / "atlas_film_score.wav"
    write_wav(wav, score())
    mp4 = out / "atlas_film.mp4"
    nframes = int(DURATION * FPS)
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium",
         "-b:v", "4M", "-maxrate", "6M", "-bufsize", "8M",  # per-frame grain defeats CRF (~1 GB)
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-16:TP=-1.5",
         "-movflags", "+faststart", "-shortest", str(mp4)],
        stdin=subprocess.PIPE)
    with Pool(args.workers, initializer=init_ctx) as pool:
        for k, buf in enumerate(pool.imap(render, range(nframes), chunksize=8)):
            ff.stdin.write(buf)
            if k % (FPS * 10) == 0:
                print(f"  {k / FPS:5.0f}s / {DURATION:.0f}s", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"wrote {mp4}")


if __name__ == "__main__":
    main()
