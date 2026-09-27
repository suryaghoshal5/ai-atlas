"""Atlas film, 90-second cut, in landscape (16:9) and vertical (9:16).

Same grammar, palette, data and score synthesiser as insights.film (the 2:36
long cut); this module re-times the story to 90 s and lays every scene out for
either orientation. Paced for reading (one idea per card, each held long
enough to read on a phone), which at 90 s means 15 cards. Kept: cold open,
title, signal, the imported forecast, the task count and the rubric, the atlas
(full-frame reveal), the wage bill, gender flip and entry rung, the canary, end
card. Cut from the long version: the 0.27x usage figure, the Stanford -13/-19
beat, 122 groups / 463M build steps, the pay-weighted 0.155, the 2.4x
crosswalk mirror, the bank teller and the coda.

Vertical is 1080x1920 with all type and data inside the central 1080x1350
(4:5) zone, which the letterbox bars frame; `--crop45` also writes a 4:5 file
cut from that zone for the LinkedIn feed.

Presentation layer only. Figures are quoted from the published essay or read
from outputs/atlas_grid and outputs/tables/tab6_2_event_study_PRELIMINARY.txt;
the end card carries the PRELIMINARY stamp (D6).

    PYTHONPATH=src python -m insights.film_short --orient vertical --crop45
    PYTHONPATH=src python -m insights.film_short --orient landscape
    PYTHONPATH=src python -m insights.film_short --orient vertical --stills 3,45
"""

from __future__ import annotations

import argparse
import math
import random
import subprocess
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from atlas_common import outputs_dir, run_seed
from insights.film import (BG, BIN_RGB, FPS, INK, INK2, INK3, RED, VERBS, bin_rgb, clamp, ease,
                           ease_out, env, fmt_int, font, lines, load_event_study, load_grid, mix, rule,
                           score, text, write_wav)

OUT = outputs_dir() / "film"

ORIENTS = {"landscape": (1920, 1080, 138), "vertical": (1080, 1920, 285)}
W, H, BAR, P = 1920, 1080, 138, False
CX, CY = W / 2, H / 2


def configure(orient: str):
    global W, H, BAR, P, CX, CY
    W, H, BAR = ORIENTS[orient]
    P = orient == "vertical"
    CX, CY = W / 2, H / 2


def pk(land, port):
    """Pick the landscape or portrait value."""
    return port if P else land


def mono(size):
    """Mono labels, 1.3x on vertical so they stay legible on a phone."""
    return font("mono", round(size * pk(1.0, 1.3)))


# ================================================================ timeline
# Paced for reading: every card is held >= ~1.2 s + words / 3 per second of
# clear screen, with 0.6-0.9 s fades. 90 s holds 15 cards at that pace, so
# this cut keeps one idea per card and drops the rest (see module docstring).
T = {
    "cold": (0.0, 6.0), "title": (6.0, 11.0), "signal": (11.0, 22.0), "fear": (22.0, 27.5),
    "build": (27.5, 38.5), "atlas": (38.5, 57.5), "money": (57.5, 63.5), "who": (63.5, 74.0),
    "canary": (74.0, 84.0), "end": (84.0, 90.0),
}
DURATION = T["end"][1]
IMAX = [(38.6, 57.2)]
CLOCK_STOP = T["canary"][0] + 6.4
FI, FO = 0.7, 0.5  # default fade in / out

CUES = {
    "duration": DURATION,
    "rate_pts": [(0, 1.0), (11.0, 1.1), (38.5, 1.5), (57.5, 1.5), (74.0, 2.0), (CLOCK_STOP, 3.2)],
    "clock_stop": CLOCK_STOP,
    "tick_ramp": (38.5, CLOCK_STOP),
    "watch2": (84.3, 89.0),
    "drone_mute": (CLOCK_STOP, 84.0),
    "shepard": [(27.7, 38.5, 0.028), (74.5, CLOCK_STOP, 0.04)],
    "braams": [(0.8, 0.55), (6.3, 0.35), (39.0, 0.7), (52.5, 0.6), (CLOCK_STOP + 0.5, 0.4)],
    "end_note": 84.4,
}


def bars(t):
    k = 0.0
    for a, b in IMAX:
        k = max(k, min(ease((t - a) / 0.9), ease((b - t) / 0.9)))
    return BAR * (1 - k)


def tag(d, t, key, label):
    a, b = T[key]
    text(d, label, (CX, BAR + pk(56, 70)), mono(pk(18, 20)), RED, env(t, a + 0.2, b - 0.15, 0.6, 0.4),
         track=0.3)


def stack(d, rows, y, f, c, a, lead=1.35):
    lines(d, rows, CX, y, f, c, a, lead=lead)


def tracked_rows(d, rows, y0, f, c, a, lead=1.35, track=0.3):
    for i, r in enumerate(rows):
        text(d, r, (CX, y0 + i * f.size * lead), f, c, a, track=track)


# ------------------------------------------------------------------ scenes
def s_cold(d, t, ctx):
    a = env(t, 0.7, 5.8, 0.4, 0.3)
    k = ease_out((t - 0.7) / 2.0)
    text(d, fmt_int(463_000_000 * k), (CX, CY - 20), font("title_xl", pk(150, 112)), INK, a, track=0.08)
    text(d, "WORKERS.", (CX, CY + pk(105, 90)), font("title", 28), INK2, env(t, 3.0, 5.8, FI, 0.3), track=0.6)
    text(d, "ONE QUESTION.", (CX, CY + pk(160, 145)), font("title", 28), RED, env(t, 3.9, 5.8, FI, 0.3),
         track=0.6)


def s_title(d, t, ctx):
    t0, t1 = T["title"]
    a = env(t, t0 + 0.3, t1 - 0.2, 0.9, 0.6)
    rows = pk(["WHERE DOES AI", "ACTUALLY LAND IN INDIA?"], ["WHERE DOES AI", "ACTUALLY LAND", "IN INDIA?"])
    f = font("title", pk(76, 64))
    step = f.size * 1.3
    y0 = CY - 10 - step * (len(rows) - 1) / 2
    tracked_rows(d, rows, y0, f, INK, a, lead=1.3)
    b = env(t, t0 + 1.3, t1 - 0.2, FI, 0.6)
    yb = y0 + step * (len(rows) - 1) + pk(100, 110)
    if P:
        stack(d, ["AN ATLAS OF 463 MILLION WORKERS", "SURYADIP GHOSHAL"], yb, mono(20), INK2, b, 1.6)
    else:
        text(d, "AN ATLAS OF 463 MILLION WORKERS  ·  SURYADIP GHOSHAL", (CX, yb), mono(20), INK2, b, track=0.22)


def s_signal(d, t, ctx):
    t0, t1 = T["signal"]
    tag(d, t, "signal", "I · THE SIGNAL")
    text(d, "45%", (CX, CY - 40), font("title_l", pk(190, 200)), RED, env(t, t0 + 0.2, t0 + 5.4, FI, FO))
    stack(d, pk(["of Indian Claude usage maps to software occupations.", "The highest share of any country."],
                ["of Indian Claude usage maps", "to software occupations.", "The highest share of any country."]),
          CY + pk(150, 180), font("body", pk(34, 38)), INK2, env(t, t0 + 0.8, t0 + 5.4, FI, FO))
    text(d, "ANTHROPIC ECONOMIC INDEX  ·  INDIA BRIEF (FEB 2026)", (CX, H - BAR - 44), mono(pk(17, 16)),
         INK2, env(t, t0 + 0.8, t0 + 5.4, FI, FO) * 0.8, track=0.08)
    stack(d, pk(["A few million coders met AI early."], ["A few million coders", "met AI early."]),
          CY - pk(40, 90), font("body", pk(46, 52)), INK, env(t, t0 + 5.7, t1 - 0.2, FI, FO))
    stack(d, pk(["450 million other workers have barely met it."], ["450 million other workers", "have barely met it."]),
          CY + pk(40, 90), font("body", pk(46, 52)), RED, env(t, t0 + 6.6, t1 - 0.2, FI, FO))


def s_fear(d, t, ctx):
    t0, t1 = T["fear"]
    tag(d, t, "fear", "II · THE IMPORTED FEAR")
    q = pk(["“AI could wipe out half of all", "entry-level white-collar jobs.”"],
           ["“AI could wipe out", "half of all entry-level", "white-collar jobs.”"])
    stack(d, q, CY - pk(40, 60), font("title_l", 58), INK, env(t, t0 + 0.2, t1 - 0.2, FI, FO), lead=1.3)
    text(d, "DARIO AMODEI  ·  AXIOS  ·  MAY 2025", (CX, CY + pk(90, 110)), mono(20), INK2,
         env(t, t0 + 1.0, t1 - 0.2, FI, FO), track=0.2)
    stack(d, pk(["It rests on US occupation lists and US task descriptions."],
                ["It rests on US occupation lists", "and US task descriptions."]),
          CY + pk(190, 250), font("body", pk(30, 36)), INK2, env(t, t0 + 2.2, t1 - 0.2, FI, FO))


def s_build(d, t, ctx):
    t0, t1 = T["build"]
    tag(d, t, "build", "III · THE BUILD")
    cy = CY - pk(60, 80)
    a = env(t, t0 + 0.2, t0 + 5.0, FI, FO)
    if a > 0:
        ls = t - t0 - 0.2
        text(d, fmt_int(18622 * ease_out(ls / 2.0)), (CX, cy - 60), font("title_l", pk(130, 140)), INK, a)
        text(d, "TASK STATEMENTS", (CX, cy + pk(40, 50)), mono(20), INK2, a, track=0.3)
        text(d, VERBS[int(ls / 0.6) % len(VERBS)], (CX, cy + pk(110, 130)), font("body", pk(36, 42)), RED, a)
        stack(d, pk(["parsed from India's official occupation descriptions (NCO-2015)"],
                    ["parsed from India's official", "occupation descriptions (NCO-2015)"]),
              cy + pk(180, 230), font("body", pk(26, 30)), INK2, a)
    a2 = env(t, t0 + 5.3, t1 - 0.2, FI, FO)
    if a2 > 0:
        ls = t - t0 - 5.3
        q = pk(["Would access to an LLM cut the time this task takes", "by at least half, at equal quality?"],
               ["Would access to an LLM", "cut the time this task takes", "by at least half,", "at equal quality?"])
        text(d, "ONE QUESTION, EVERY TASK", (CX, cy - pk(150, 230)), mono(20), INK2, a2, track=0.3)
        stack(d, q, cy - pk(40, 60), font("title_l", pk(44, 46)), INK, a2)
        labels = [("E0", "not exposed"), ("E1", "chat alone"), ("E2", "needs tooling")]
        for j, (k, v) in enumerate(labels):
            x = CX + (j - 1) * pk(380, 300)
            aj = a2 * ease((ls - 1.4 - j * 0.5) / 0.5)
            text(d, k, (x, cy + pk(100, 160)), font("title", 40), RED if j else INK2, aj)
            text(d, v, (x, cy + pk(145, 205)), font("body", pk(24, 28)), INK2, aj)


def grid_layout(bands):
    cols, pitch, gap = pk((30, 33, 4), (24, 38, 5))
    x0 = pk(150, (W - cols * pitch + gap) / 2)
    y = pk(150, BAR + 40)
    lay, heads = [], []
    for b in bands:
        heads.append((b, y))
        y += 40
        for i, beta in enumerate(b["squares"]):
            r, c = divmod(i, cols)
            lay.append((x0 + c * pitch, y + r * pitch, pitch - gap, beta, b["key"]))
        y += math.ceil(len(b["squares"]) / cols) * pitch + 20
    return lay, heads, (x0, x0 + cols * pitch - gap, y)


def s_atlas(d, t, ctx):
    t0, t1 = T["atlas"]
    lay, heads, (gx0, gx1, gy1) = ctx["grid"]
    ga = env(t, t0 + 0.3, t1 - 0.3, 0.3, 0.8)
    if ga <= 0:
        return
    r0, r1 = t0 + 9.2, t0 + 13.8          # sector rows
    hi = "agriculture" if r0 <= t < r0 + 1.8 else None
    dim = 1 - 0.78 * env(t, t0 + 13.6, t1, 0.8, 0.3)
    for i, (x, y, s, beta, key) in enumerate(lay):
        k = ease_out((t - (t0 + 0.5 + 3.2 * i / len(lay) + ctx["jitter"][i])) / 0.5)
        if k <= 0:
            continue
        a = ga * k * dim * (0.3 if hi and key != hi else 1)
        dy = (1 - k) * -18
        d.rectangle([x, y + dy, x + s, y + dy + s], fill=mix(bin_rgb(beta), a))
    for b, y in heads:
        ha = ga * env(t, t0 + 1.0, t1, 0.8, 0.8) * dim * (0.3 if hi and b["key"] != hi else 1)
        text(d, b["label"].upper(), (gx0, y + 14), mono(17), INK, ha, "lm", track=0.2)
        text(d, f"{b['workers_m']:.0f}M  ·  β {b['beta']:.3f}", (gx1, y + 14), mono(17), INK2, ha, "rm",
             track=0.06)
    la = ga * env(t, t0 + 3.0, t1, 0.8, 0.8) * dim
    if P:
        text(d, "ONE SQUARE = ONE MILLION WORKERS  ·  REDDER = MORE EXPOSED", (CX, gy1 + 6), mono(16), INK2, la,
             track=0.1)
    else:
        lx, ly = 150, H - 120
        text(d, "ONE SQUARE = ONE MILLION WORKERS  ·  COLOUR = β EXPOSURE", (lx, ly - 34), mono(16), INK2,
             la, "lm", track=0.14)
        for j, c in enumerate(BIN_RGB):
            d.rectangle([lx + j * 80, ly, lx + j * 80 + 76, ly + 12], fill=mix(c, la))
            text(d, ["0", ".05", ".10", ".20", ".35", ".50+"][j], (lx + j * 80, ly + 30), mono(15), INK3, la, "lm")

    # ---- "5 in 6": right panel (landscape) or under the grid (vertical)
    a1 = env(t, t0 + 4.2, t0 + 9.0, FI, FO)
    g = ease_out((t - t0 - 4.8) / 1.2)
    if P:
        y0 = gy1 + 90
        text(d, "5 in 6", (CX - 60, y0), font("title_l", 96), INK, a1, "rm")
        lines(d, ["tasks came back", "marked no exposure."], CX - 20, y0, font("body", 32), INK2, a1, anchor="l")
        bx, bw, by = (W - 720) / 2, 720, y0 + 95
        tx, ty, tanchor = CX, by + 50, "mm"
    else:
        rx = 1270
        text(d, "5 in 6", (rx, 380), font("title_l", 120), INK, a1, "lm")
        lines(d, ["tasks came back marked", "no exposure."], rx, 505, font("body", 34), INK2, a1, anchor="l")
        bx, bw, by = rx, 520, 600
        tx, ty, tanchor = rx, 655, "lm"
    x = bx
    for n, c in [(15498, INK3), (1946, RED), (1150, (126, 31, 28))]:
        w = bw * n / 18594 * g
        d.rectangle([x, by, x + w, by + 22], fill=mix(c, a1))
        x += w
    text(d, "E0 15,498   E1 1,946   E2 1,150", (tx, ty), mono(17), INK2, a1, tanchor, track=0.04)

    rows = [("AGRICULTURE", "194M", "0.06"), ("CONSTRUCTION", "60M", "0.03"), ("IT & COMMUNICATION", "7M", "0.54")]
    for j, (lab, m, b) in enumerate(rows):
        a = env(t, r0 + j * 0.6, r1, FI, FO)
        if P:
            y = gy1 + 105 + j * 76
            text(d, lab, (110, y), mono(18), INK2, a, "lm", track=0.16)
            text(d, m, (720, y), font("title_l", 46), INK, a, "rm")
            text(d, b, (W - 110, y), font("title_l", 46), RED if j == 2 else INK, a, "rm")
        else:
            y = 420 + j * 120
            text(d, lab, (1270, y - 26), mono(18), INK2, a, "lm", track=0.2)
            text(d, m, (1270, y + 22), font("title_l", 58), INK, a, "lm")
            text(d, b, (1630, y + 22), font("title_l", 58), RED if j == 2 else INK, a, "lm")
    ah = env(t, r0, r1, FI, FO)
    if P:
        text(d, "WORKERS", (720, gy1 + 55), mono(14), INK3, ah, "rm", track=0.2)
        text(d, "β", (W - 110, gy1 + 55), mono(16), INK3, ah, "rm")
    else:
        text(d, "WORKERS", (1270, 330), mono(14), INK3, ah, "lm", track=0.2)
        text(d, "β", (1630, 330), mono(16), INK3, ah, "lm")

    a3 = env(t, t0 + 14.0, t1 - 0.3, FI, 0.6)
    mx, my = pk((1520, CY - 60), (CX, CY - 80))
    text(d, "0.086", (mx, my), font("title_xl", pk(190, 210)), INK, a3)
    text(d, "ECONOMY-WIDE MEAN EXPOSURE", (mx, my + pk(140, 150)), mono(20), INK2, a3, track=0.24)
    text(d, "For most of India, it is not close.", (mx, my + pk(210, 220)), font("body", pk(36, 40)), RED,
         env(t, t0 + 14.8, t1 - 0.3, FI, 0.6))


def hbar(d, x, y, h, frac, c, a, maxw):
    d.rectangle([x, y, x + maxw, y + h], fill=mix(INK3, a * 0.35))
    d.rectangle([x, y, x + maxw * frac, y + h], fill=mix(c, a))


def s_money(d, t, ctx):
    t0, t1 = T["money"]
    tag(d, t, "money", "IV · FOLLOW THE MONEY")
    a = env(t, t0 + 0.2, t1 - 0.2, FI, FO)
    g = ease_out((t - t0 - 0.6) / 1.6)
    x, mw = pk((CX - 380, 760), (130, 640))
    yt = CY - pk(110, 170)
    text(d, "OCCUPATIONS SCORING β ≥ 0.5", (CX, yt - pk(90, 110)), mono(18), INK3, a, track=0.2)
    text(d, "SHARE OF WORKERS", (x, yt - 20), mono(18), INK2, a, "lm", track=0.2)
    hbar(d, x, yt + 5, 30, 0.019 / 0.08 * g, INK, a, mw)
    text(d, f"{1.9 * g:.1f}%", (x + mw + 24, yt + 20), font("title_l", 46), INK, a, "lm")
    text(d, "SHARE OF THE WAGE BILL", (x, yt + 100), mono(18), INK2, a, "lm", track=0.2)
    hbar(d, x, yt + 125, 30, 0.071 / 0.08 * g, RED, a, mw)
    text(d, f"{7.1 * g:.1f}%", (x + mw + 24, yt + 140), font("title_l", 46), RED, a, "lm")
    a2 = env(t, t0 + 2.4, t1 - 0.2, FI, FO)
    tracked_rows(d, pk(["AN INCOME STORY", "BEFORE A JOBS-COUNT STORY."], ["AN INCOME STORY", "BEFORE A", "JOBS-COUNT STORY."]),
                 yt + pk(290, 330), font("title", pk(32, 36)), INK, a2, lead=1.5)


def pair(d, x, label, w_val, m_val, a, g, red_w, base):
    text(d, label, (x - 5, base + 75), mono(18), INK2, a, track=0.24)
    for j, (lab, v) in enumerate([("WOMEN", w_val), ("MEN", m_val)]):
        bx = x - 110 + j * 150
        hgt = 1250 * v * g
        c = RED if (j == 0 and red_w) else INK if j == 0 else INK2
        d.rectangle([bx, base - hgt, bx + 70, base], fill=mix(c, a))
        text(d, f"{v:.2f}", (bx + 35, base - hgt - 30), font("title_l", 34), c, a * g)
        text(d, lab, (bx + 35, base + 30), mono(16), INK2, a, track=0.2)


def s_who(d, t, ctx):
    t0, t1 = T["who"]
    tag(d, t, "who", "V · WHO, EXACTLY")
    base = CY + pk(150, 170)
    e0 = t0 + 5.5
    a = env(t, t0 + 0.2, e0, FI, FO)
    text(d, "MEAN EXPOSURE, WOMEN AND MEN", (CX, CY - pk(270, 330)), mono(18), INK3, a, track=0.2)
    pair(d, CX - pk(330, 250), "ALL WORKERS", 0.07, 0.09, a, ease_out((t - t0 - 0.4) / 1.2), False, base)
    pair(d, CX + pk(330, 250), pk("ORGANISED SECTOR", "ORGANISED"), 0.26, 0.25, env(t, t0 + 1.4, e0, FI, FO),
         ease_out((t - t0 - 1.6) / 1.2), True, base)
    text(d, "THE SIGN REVERSES.", (CX, base + pk(170, 200)), font("title", pk(30, 34)), RED,
         env(t, t0 + 2.8, e0, FI, FO), track=0.34)
    a2 = env(t, e0 + 0.2, t1 - 0.2, FI, FO)
    hdr = pk(["WHITE-COLLAR WORKERS IN HIGH-EXPOSURE OCCUPATIONS"], ["WHITE-COLLAR WORKERS", "IN HIGH-EXPOSURE OCCUPATIONS"])
    for i, r in enumerate(hdr):
        text(d, r, (CX, CY - pk(190, 230) + i * 30), mono(18), INK2, a2, track=0.2)
    dx = pk(260, 230)
    text(d, "22%", (CX - dx, CY - 40), font("title_l", pk(170, 150)), RED, a2)
    text(d, "AGED 18 TO 29", (CX - dx, CY + 70), mono(18), INK, a2, track=0.2)
    text(d, "11%", (CX + dx, CY - 40), font("title_l", pk(170, 150)), INK2, a2)
    text(d, "THEIR SENIORS", (CX + dx, CY + 70), mono(18), INK2, a2, track=0.2)
    stack(d, pk(["About 3.5 million young workers hold those rungs."],
                ["About 3.5 million young workers", "hold those rungs."]),
          CY + pk(170, 190), font("body", pk(30, 36)), INK2, env(t, e0 + 1.0, t1 - 0.2, FI, FO))


def s_canary(d, t, ctx):
    t0, t1 = T["canary"]
    tag(d, t, "canary", "VI · THE CANARY")
    rows = ctx["event"]
    a = env(t, t0 + 0.2, CLOCK_STOP - 0.1, FI, 0.3)
    if a > 0:
        x0, x1 = pk((260, W - 260), (100, W - 100))
        yc, sc, lim = CY + pk(50, 60), pk(110, 150), 2.0
        n = len(rows)
        xs = [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]
        rule(d, x0 - 20, x1 + 20, yc, a, INK3, 1)
        ref = [i for i, r in enumerate(rows) if (r[0], r[1]) == (2022, 4)][0]
        xr = (xs[ref] + xs[ref + 1]) / 2
        d.line([(xr, yc - lim * sc - 20), (xr, yc + lim * sc + 20)], fill=mix(RED, a * 0.8), width=1)
        text(d, "CHATGPT  ·  NOV 2022", (xr + 12, yc - lim * sc - 10), mono(16), RED, a, "lm", track=0.14)
        shown = (t - t0 - 0.5) / 2.8 * n
        for i, (yr, q, b, se) in enumerate(rows):
            if i > shown:
                break
            c = RED if (yr, q) > (2022, 4) else INK2
            lo, hi = b - 1.96 * se, b + 1.96 * se
            ylo, yhi = yc - clamp(hi, -lim, lim) * sc, yc - clamp(lo, -lim, lim) * sc
            d.line([(xs[i], ylo), (xs[i], yhi)], fill=mix(c, a * 0.55), width=2)
            for yy, v in ((ylo, hi), (yhi, lo)):
                if abs(v) > lim:
                    d.line([(xs[i] - 5, yy), (xs[i] + 5, yy)], fill=mix(c, a * 0.55), width=2)
            yb = yc - clamp(b, -lim, lim) * sc
            if abs(b) > lim:
                d.polygon([(xs[i] - 7, yb - 5), (xs[i] + 7, yb - 5), (xs[i], yb + 8)], outline=mix(c, a))
            else:
                d.ellipse([xs[i] - 6, yb - 6, xs[i] + 6, yb + 6], fill=mix(c, a))
            if q == 1 and yr in (2021, 2023, 2025):
                text(d, str(yr), (xs[i], yc + lim * sc + 40), mono(16), INK3, a)
        cap = pk(["YOUNG-WORKER NET PAYROLL ADDITIONS × EXPOSURE  ·  EPFO  ·  95% CI  ·  2020 COVID QUARTERS CLIPPED"],
                 ["YOUNG-WORKER NET PAYROLL ADDITIONS × EXPOSURE", "EPFO  ·  95% CI  ·  2020 COVID QUARTERS CLIPPED"])
        for i, r in enumerate(cap):
            text(d, r, (CX, yc + lim * sc + 85 + i * 28), mono(pk(16, 15)), INK2, a, track=0.08)
        stack(d, ["The point estimates lean negative.", "None is statistically significant."],
              yc - lim * sc - pk(85, 120), font("body", pk(32, 36)), INK, env(t, t0 + 3.2, CLOCK_STOP - 0.1, FI, 0.3))
    a3 = env(t, CLOCK_STOP + 0.5, t1 - 0.2, 0.9, 0.5)
    tracked_rows(d, pk(["THE CANARY HAS NOT SUNG."], ["THE CANARY", "HAS NOT SUNG."]), CY - pk(0, 40),
                 font("title", pk(52, 58)), INK, a3, lead=1.4, track=0.32)


def s_end(d, t, ctx):
    t0, t1 = T["end"]
    a = env(t, t0 + 0.3, t1, 0.8, 0.9)
    rows = pk(["EVERY SQUARE OPENS TO ITS TASKS."], ["EVERY SQUARE OPENS", "TO ITS TASKS."])
    for i, r in enumerate(rows):
        text(d, r, (CX, CY - pk(150, 330) + i * 56), font("title", 34), INK, a, track=0.3)
    links = [("THE ATLAS", "suryaghoshal5.github.io/ai-atlas"),
             ("THE ESSAY", "suryadipghoshal.substack.com/p/463-million-workers-one-question"),
             ("THE CODE", "github.com/suryaghoshal5/ai-atlas")]
    for j, (k, v) in enumerate(links):
        aj = env(t, t0 + 0.8 + j * 0.3, t1, FI, 0.9)
        if P:
            y = CY - 150 + j * 120
            text(d, k, (CX, y), mono(18), RED, aj, track=0.24)
            text(d, v, (CX, y + 40), font("body_r", 26), INK, aj)
        else:
            y = CY - 40 + j * 62
            text(d, k, (CX - 440, y), mono(18), RED, aj, "lm", track=0.24)
            text(d, v, (CX - 250, y), font("body_r", 30), INK, aj, "lm")
    ap = env(t, t0 + 1.6, t1, FI, 0.9)
    pre = pk(["PRELIMINARY  ·  TASK SCORES ARE LLM-ONLY; HUMAN VALIDATION PENDING  ·  PLFS 2023-24 × NCO-2015"],
             ["PRELIMINARY  ·  TASK SCORES ARE LLM-ONLY;", "HUMAN VALIDATION PENDING  ·  PLFS 2023-24 × NCO-2015"])
    for i, r in enumerate(pre):
        text(d, r, (CX, CY + pk(210, 230) + i * 28), mono(pk(16, 15)), INK2, ap, track=0.1)
    text(d, "SURYADIP GHOSHAL", (CX, CY + pk(260, 320)), font("title", 22), INK2, ap, track=0.5)


SCENES = [(T[k], f) for k, f in [
    ("cold", s_cold), ("title", s_title), ("signal", s_signal), ("fear", s_fear), ("build", s_build),
    ("atlas", s_atlas), ("money", s_money), ("who", s_who), ("canary", s_canary), ("end", s_end)]]

# ------------------------------------------------------------------ render
_CTX: dict = {}


def init_ctx(orient: str):
    configure(orient)
    rnd = random.Random(run_seed())
    grid = grid_layout(load_grid())
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    rng = np.random.default_rng(run_seed())
    _CTX.update(
        grid=grid, jitter=[rnd.uniform(0, 0.4) for _ in grid[0]], event=load_event_study(),
        vignette=(1 - 0.38 * np.clip(r - 0.35, 0, None) ** 1.6)[..., None].astype(np.float32),
        grain=[rng.normal(0, 5.0, (H, W, 1)).astype(np.float32) for _ in range(8)],
    )


def push(t):
    for (a, b), _ in SCENES:
        if a <= t < b:
            return 1.0 + 0.02 * (t - a) / (b - a)
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
    arr = np.asarray(img, dtype=np.float32) * _CTX["vignette"] + _CTX["grain"][i % 8]
    bh = int(round(bars(t)))
    if bh:
        arr[:bh] = 0
        arr[H - bh:] = 0
    return np.clip(arr, 0, 255).astype(np.uint8).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orient", choices=list(ORIENTS), default="vertical")
    ap.add_argument("--crop45", action="store_true", help="vertical only: also write the 4:5 feed crop")
    ap.add_argument("--stills", help="comma-separated seconds; write PNGs only")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    init_ctx(args.orient)
    stem = f"atlas_film_90s_{'9x16' if P else '16x9'}"

    if args.stills:
        for s in args.stills.split(","):
            Image.frombytes("RGB", (W, H), render(int(float(s) * FPS))).save(
                out / f"{stem}_still_{float(s):05.1f}.png")
        return

    wav = out / "atlas_film_90s_score.wav"
    write_wav(wav, score(CUES))
    mp4 = out / f"{stem}.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium",
         "-b:v", "4M", "-maxrate", "6M", "-bufsize", "8M",  # per-frame grain defeats CRF
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-16:TP=-1.5",
         "-movflags", "+faststart", "-shortest", str(mp4)],
        stdin=subprocess.PIPE)
    nframes = int(DURATION * FPS)
    with Pool(args.workers, initializer=init_ctx, initargs=(args.orient,)) as pool:
        for k, buf in enumerate(pool.imap(render, range(nframes), chunksize=8)):
            ff.stdin.write(buf)
            if k % (FPS * 15) == 0:
                print(f"  {k / FPS:4.0f}s / {DURATION:.0f}s", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"wrote {mp4}")
    if P and args.crop45:
        crop = out / "atlas_film_90s_4x5.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", f"crop={W}:1350:0:{BAR}",
                        "-c:v", "libx264", "-preset", "medium", "-b:v", "3.5M", "-maxrate", "5M", "-bufsize", "7M",
                        "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(crop)], check=True)
        print(f"wrote {crop}")


if __name__ == "__main__":
    main()
