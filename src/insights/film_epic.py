"""Atlas film, 90-second vertical cut, re-dressed in an S. S. Rajamouli grammar.

Same cards, copy, data and reading pace as insights.film_short (the paced
90 s cut); only the dress changes:
    look   gold-and-fire palette on a deep maroon ground, Linux Libertine
           display serif, metallic gold on the big numbers, god-rays, rising
           embers, bloom, and an "elevation" camera punch with a flash on
           every reveal
    sound  war-drum ostinato that climbs in tempo through the film, choir
           pads moving Dm -> Gm -> C -> A (dominant), brass-and-boom impacts,
           drums cut dead before "the canary has not sung", D-major choir on
           the end card
Section tags become chapter cards (CHAPTER I ... VII).

Presentation layer only; figures as in insights.film_short. PRELIMINARY
stamp kept on the end card (D6).

    PYTHONPATH=src python -m insights.film_epic                 # 9:16 + 4:5 crop
    PYTHONPATH=src python -m insights.film_epic --stills 3,40,76
"""

from __future__ import annotations

import argparse
import math
import subprocess
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import insights.film as film
import insights.film_short as fs
from atlas_common import run_seed

SR, FPS = film.SR, film.FPS

# ------------------------------------------------------------------ theme
BG = (18, 8, 6)
INK = (247, 234, 204)       # ivory
INK2 = (176, 160, 140)      # parchment (neutral, so gold stays the only accent)
INK3 = (96, 66, 44)         # dark bronze
GOLD = (242, 172, 58)       # the accent (replaces the Nolan red)
FIRE = (236, 84, 26)        # post-ChatGPT estimates in the canary chart, set apart from gold
BIN_RGB = [(40, 28, 24), (64, 40, 30), (110, 58, 26), (172, 92, 26), (234, 144, 38), (255, 214, 110)]
METAL = {  # vertical gradient stops for big type
    GOLD: [(255, 242, 196), (248, 196, 86), (220, 134, 34), (150, 74, 18)],
    INK: [(255, 253, 244), (248, 234, 204), (212, 186, 144)],
}
# Linux Libertine (apt install fonts-linuxlibertine; on macOS install the OTFs to ~/Library/Fonts)
FONTS = {
    "title": "LinLibertine_RB.otf",
    "title_l": "LinLibertine_DR.otf",
    "title_xl": "LinLibertine_DR.otf",
    "body": "LinLibertine_R.otf",
    "body_r": "LinLibertine_R.otf",
    "body_m": "LinLibertine_RZ.otf",
    "mono": "LinLibertine_RZ.otf",
}

_orig_text = film.text


def mix(c, a, bg=BG):
    return tuple(int(bg[i] + (c[i] - bg[i]) * a) for i in range(3))


def _gradient(h, stops):
    s = np.array(stops, np.float32)
    n = len(s) - 1
    y = np.linspace(0, 1, max(h, 1), dtype=np.float32) * n
    i = np.minimum(y.astype(int), n - 1)
    f = (y - i)[:, None]
    return s[i] * (1 - f) + s[i + 1] * f  # (h, 3)


# copy that names the Nolan palette, restated for this grade
SUBS = {"ONE SQUARE = ONE MILLION WORKERS  ·  REDDER = MORE EXPOSED":
        "ONE SQUARE = ONE MILLION WORKERS  ·  BRIGHTER = MORE EXPOSED"}


def text(d, s, xy, f, c=INK, a=1.0, anchor="mm", track=0.0):
    """film.text, plus metallic gradient fill for display-size gold/ivory type."""
    if a <= 0.004 or not s:
        return
    s = SUBS.get(s, s)
    if f.size < 90 or c not in METAL:
        return _orig_text(d, s, xy, f, c, a, anchor, track)
    im = d._image
    mask = Image.new("L", im.size, 0)
    md = ImageDraw.Draw(mask)
    if not track:
        md.text(xy, s, font=f, fill=255, anchor=anchor)
    else:
        sp = track * f.size
        widths = [f.getlength(ch) for ch in s]
        x, y = xy
        x -= {"l": 0, "m": (sum(widths) + sp * (len(s) - 1)) / 2,
              "r": sum(widths) + sp * (len(s) - 1)}[anchor[0]]
        for ch, w in zip(s, widths):
            md.text((x, y), ch, font=f, fill=255, anchor="l" + anchor[1])
            x += w + sp
    bb = mask.getbbox()
    if not bb:
        return
    m = mask.crop(bb)
    if a < 0.999:
        m = Image.fromarray((np.asarray(m, np.float32) * a).astype(np.uint8))
    g = _gradient(bb[3] - bb[1], METAL[c])
    grad = np.repeat(g[:, None, :], bb[2] - bb[0], axis=1).astype(np.uint8)
    im.paste(Image.fromarray(grad, "RGB"), bb[:2], m)


def chapter_tag(d, t, key, label):
    """'I · THE SIGNAL' -> a chapter card: ornament rule, CHAPTER I, name."""
    a0, b0 = fs.T[key]
    a = film.env(t, a0 + 0.2, b0 - 0.15, 0.7, 0.4)
    if a <= 0.004:
        return
    num, name = [p.strip() for p in label.split("·", 1)]
    cx, y = fs.CX, fs.BAR + 64
    text(d, f"CHAPTER {num}", (cx, y), film.font("mono", 22), GOLD, a, track=0.42)
    text(d, name, (cx, y + 40), film.font("title", 30), INK, a, track=0.24)
    w = 170 * film.ease_out((t - a0 - 0.2) / 1.2)
    for sgn in (-1, 1):
        x0 = cx + sgn * 150
        d.line([(x0, y), (x0 + sgn * w, y)], fill=mix(GOLD, a * 0.8), width=2)
        xd = x0 + sgn * w
        d.polygon([(xd, y - 6), (xd + 6, y), (xd, y + 6), (xd - 6, y)], fill=mix(GOLD, a))


def apply_theme():
    for mod in (film, fs):
        mod.BG, mod.INK, mod.INK2, mod.INK3, mod.RED = BG, INK, INK2, INK3, GOLD
        mod.mix, mod.text = mix, text
    film.BIN_RGB[:] = BIN_RGB
    film.FONT_FILES.update(FONTS)
    film._fonts.clear()
    fs.tag = chapter_tag
    fs.POST = FIRE


apply_theme()

# --------------------------------------------------------------- impacts
# (time, strength): camera punch + flash + drum boom on every reveal
IMPACTS = [(2.7, 1.0), (6.3, 0.8), (11.2, 0.8), (22.2, 0.5), (27.7, 0.6), (39.0, 0.8), (52.5, 1.0),
           (57.7, 0.5), (63.7, 0.7), (fs.CLOCK_STOP + 0.5, 1.0), (fs.T["mirror"][0] + 1.4, 0.9),
           (fs.T["end"][0] + 0.3, 0.4)]


def punch(t):
    z = dx = dy = fl = 0.0
    for ti, s in IMPACTS:
        if t >= ti:
            k = t - ti
            z += 0.055 * s * math.exp(-k / 0.28)
            sh = 16 * s * math.exp(-k / 0.16)
            dx += sh * math.sin(k * 71 + ti)
            dy += sh * math.cos(k * 53 + ti * 2)
            fl += 0.38 * s * math.exp(-k / 0.13)
    return z, dx, dy, fl


# ------------------------------------------------------------- post FX
_FX: dict = {}


def init_fx():
    fs.init_ctx("vertical")
    W, H = fs.W, fs.H
    rng = np.random.default_rng(run_seed())
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    glow = np.exp(-(((xx - W / 2) / (0.55 * W)) ** 2 + ((yy - 0.36 * H) / (0.42 * H)) ** 2))
    qh, qw = H // 4, W // 4
    qy, qx = np.mgrid[0:qh, 0:qw].astype(np.float32)
    sx, sy = qw / 2, -0.28 * qh
    _FX.update(
        glow=(glow[..., None] * np.array([84, 26, 8], np.float32)).astype(np.float32),
        ang=np.arctan2(qx - sx, qy - sy).astype(np.float32),
        fall=np.exp(-np.hypot(qx - sx, qy - sy) / (0.95 * qh)).astype(np.float32),
        embers=[(rng.uniform(0, W), rng.uniform(0, H + 60), rng.uniform(40, 130), rng.uniform(1.2, 3.6),
                 rng.uniform(0, 6.28), rng.uniform(2, 6)) for _ in range(150)],
        kern=np.exp(-((np.mgrid[-6:7, -6:7] ** 2).sum(0)) / 8.0).astype(np.float32),
    )


def fx(arr, t, i):
    W, H = fs.W, fs.H
    arr *= np.array([1.05, 0.97, 0.84], np.float32)
    arr += _FX["glow"] * (0.75 + 0.25 * math.sin(t * 0.6))
    # god rays from above the frame, slowly turning
    ang, fall = _FX["ang"], _FX["fall"]
    r = ((0.5 + 0.5 * np.cos(17 * ang + 0.22 * t)) ** 6 * (0.6 + 0.4 * np.cos(6 * ang - 0.15 * t))) * fall
    rays = np.asarray(Image.fromarray((np.clip(r, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR),
                      np.float32)[..., None] / 255.0
    arr += rays * np.array([56, 32, 12], np.float32)
    # rising embers
    em = np.zeros((H, W), np.float32)
    k = _FX["kern"]
    for x0, y0, sp, sz, ph, fq in _FX["embers"]:
        y = int((y0 - sp * t) % (H + 60)) - 30
        x = int(x0 + 28 * math.sin(0.8 * t + ph))
        b = sz * (0.55 + 0.45 * math.sin(fq * t + ph))
        ya, yb, xa, xb = max(y - 6, 0), min(y + 7, H), max(x - 6, 0), min(x + 7, W)
        if ya < yb and xa < xb:
            em[ya:yb, xa:xb] += b * k[ya - y + 6:yb - y + 6, xa - x + 6:xb - x + 6]
    arr += np.clip(em, 0, 4)[..., None] * np.array([60, 26, 6], np.float32)
    # bloom
    bright = np.clip(arr - 165, 0, 255).astype(np.uint8)
    small = Image.fromarray(bright).resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5))
    arr += np.asarray(small.resize((W, H), Image.BILINEAR), np.float32) * 0.9
    return arr


def render(i: int) -> bytes:
    W, H = fs.W, fs.H
    t = i / FPS
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for (a, b), fn in fs.SCENES:
        if a - 0.05 <= t <= b + 0.05:
            fn(d, t, fs._CTX)
    z, dx, dy, fl = punch(t)
    s = fs.push(t) + z
    if s > 1.0005 or abs(dx) > 0.5:
        big = img.resize((round(W * s), round(H * s)), Image.BILINEAR)
        ox = int(np.clip((big.width - W) / 2 + dx, 0, big.width - W))
        oy = int(np.clip((big.height - H) / 2 + dy, 0, big.height - H))
        img = big.crop((ox, oy, ox + W, oy + H))
    arr = fx(np.asarray(img, np.float32), t, i)
    if fl > 0.01:
        arr += fl * np.array([255, 196, 120], np.float32)
    arr = arr * fs._CTX["vignette"] + fs._CTX["grain"][i % 8]
    bh = int(round(fs.bars(t)))
    if bh:
        arr[:bh] = 0
        arr[H - bh:] = 0
    return np.clip(arr, 0, 255).astype(np.uint8).tobytes()


# ================================================================= score
N = {"D2": 73.42, "G2": 98.0, "A2": 110.0, "Bb2": 116.54, "C3": 130.81, "D3": 146.83, "E3": 164.81,
     "F3": 174.61, "F#3": 185.0, "G3": 196.0, "A3": 220.0, "Bb3": 233.08, "C4": 261.63, "C#4": 277.18,
     "D4": 293.66}
STOP = fs.CLOCK_STOP          # drums cut dead here
LINE = fs.CLOCK_STOP + 0.5    # "the canary has not sung"
CHORDS = [  # (start, end, notes, gain)
    (0.4, 11.0, ["D2", "A2", "D3"], 0.35),
    (11.0, 27.5, ["D3", "F3", "A3", "D4"], 0.45),
    (27.5, 38.5, ["G2", "D3", "G3", "Bb3"], 0.5),
    (38.5, 52.5, ["D3", "F3", "A3", "D4"], 0.6),
    (52.5, 57.5, ["Bb2", "D3", "F3", "Bb3"], 0.75),
    (57.5, 69.0, ["C3", "E3", "G3", "C4"], 0.55),
    (69.0, STOP, ["A2", "E3", "A3", "C#4"], 0.7),
    (LINE, 79.0, ["D2", "A2", "D3"], 0.5),
    (79.0, 85.0, ["D3", "F3", "A3", "D4"], 0.55),
    (85.0, 90.0, ["D3", "F#3", "A3", "D4"], 0.8),
]
GROOVE = [  # (start, end, bpm_start, bpm_end, gain)
    (11.0, 38.5, 88, 96, 0.55), (38.5, 57.5, 100, 104, 0.75), (57.5, 69.0, 108, 112, 0.8),
    (69.0, STOP, 112, 140, 1.0), (79.0, 84.6, 92, 92, 0.45),
]


def epic_score(duration=fs.DURATION) -> np.ndarray:
    from scipy.signal import fftconvolve
    n = int(duration * SR)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(run_seed())
    out = np.zeros((n, 2))

    def add(i0, sig, pan=0.0):
        m = min(sig.size, n - i0)
        if m > 0 and i0 >= 0:
            out[i0:i0 + m, 0] += sig[:m] * (1 - pan)
            out[i0:i0 + m, 1] += sig[:m] * (1 + pan)

    # --- choir "aah": detuned saw stacks shaped by two vowel formants
    def choir(t0, t1, notes, gain):
        a0, a1 = int(max(t0 - 0.4, 0) * SR), int(min(t1 + 0.6, duration) * SR)
        ts = tt[a0:a1] - tt[a0]
        dur = ts[-1] if ts.size else 0
        env = np.minimum(1, ts / 0.9) * np.minimum(1, np.maximum(dur - ts, 0) / 0.8)
        sig = np.zeros(ts.size)
        for nm in notes:
            f0 = N[nm]
            for det in (-0.004, 0.0, 0.005):
                f = f0 * (1 + det)
                vib = 1 + 0.004 * np.sin(2 * np.pi * 5.1 * ts + f)
                ph = 2 * np.pi * f * np.cumsum(vib) / SR
                for h in range(1, 24):
                    fh = f * h
                    if fh > 4000:
                        break
                    form = (np.exp(-((fh - 720) / 140) ** 2) + 0.7 * np.exp(-((fh - 1150) / 180) ** 2)
                            + 0.25 * np.exp(-((fh - 2600) / 300) ** 2))
                    sig += (0.35 / h + form) * np.sin(h * ph) / h ** 0.5
        add(a0, sig * env * gain * 0.010)

    for t0, t1, notes, g in CHORDS:
        choir(t0, t1, notes, g)

    # --- drums: low war drum + high dhol-like skin
    def drum(f0, f1, dec, noise, dur=1.2):
        ts = np.arange(int(dur * SR)) / SR
        f = f1 + (f0 - f1) * np.exp(-ts / 0.045)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-ts / dec)
        hit = rng.normal(0, 1, ts.size) * np.exp(-ts / 0.012) * noise
        return body + hit

    low = drum(150, 52, 0.42, 0.35)
    mid = drum(230, 150, 0.16, 0.5, 0.6)
    high = drum(420, 300, 0.07, 0.8, 0.3)
    pat_low = [1, 0, 0, 1, 0, 0, 1, 0]
    pat_mid = [0, 0, 1, 0, 1, 0, 0, 1]
    for t0, t1, b0, b1, g in GROOVE:
        t, step = t0, 0
        while t < t1:
            bpm = b0 + (b1 - b0) * (t - t0) / (t1 - t0)
            i0 = int(t * SR)
            if pat_low[step % 8]:
                add(i0, low * 0.55 * g, -0.1)
            if pat_mid[step % 8]:
                add(i0, mid * 0.32 * g, 0.25)
            if t > 69.0:  # accelerating rolls into the canary
                add(i0, high * 0.18 * g, -0.3)
            t += 60.0 / bpm / 2
            step += 1

    # --- impacts: reverse swell, boom, brass stab
    def impact(at, s):
        i0 = int(at * SR)
        sw = int(1.1 * SR)
        if s >= 0.8 and i0 - sw > 0:
            ts = np.arange(sw) / SR
            noise = film.hp(rng.normal(0, 1, sw), 1500) * (ts / ts[-1]) ** 3
            add(i0 - sw, noise * 0.10 * s)
        ts = np.arange(int(3.5 * SR)) / SR
        f = 32 + 70 * np.exp(-ts / 0.09)
        boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-ts / 1.1)
        boom += film.lp(rng.normal(0, 1, ts.size), 300) * np.exp(-ts / 0.25) * 0.6
        add(i0, boom * 0.75 * s)
        fc = 150 + 1600 * np.exp(-ts / 0.35) * (1 - np.exp(-ts / 0.02))
        brass = np.zeros(ts.size)
        for f0 in (N["D2"], N["A2"], N["D3"]):
            for h in range(1, 22):
                brass += 1 / h / (1 + (f0 * h / fc) ** 4) * np.sin(2 * np.pi * f0 * h * ts)
        add(i0, brass * (1 - np.exp(-ts / 0.03)) * np.exp(-ts / 1.0) * 0.13 * s)

    for at, s in IMPACTS:
        impact(at, s)

    # --- hall reverb, then the silence before the canary line is kept clean
    ir_t = np.arange(int(2.2 * SR)) / SR
    for ch in range(2):
        ir = rng.normal(0, 1, ir_t.size) * np.exp(-ir_t / 0.6)
        ir[0] = 0
        out[:, ch] += 0.018 * fftconvolve(out[:, ch], ir)[:n]
    gate = np.ones(n)
    a, b = int(STOP * SR), int((LINE - 0.02) * SR)
    gate[a:b] = 0.0
    ramp = int(0.03 * SR)
    gate[a - ramp:a] = np.linspace(1, 0, ramp)
    out *= gate[:, None]
    fade = int(1.5 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return out / (np.abs(out).max() + 1e-9) * 0.89


# ================================================================== main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", help="comma-separated seconds; write PNGs only")
    ap.add_argument("--out", default=str(fs.OUT))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    init_fx()
    stem = f"atlas_film_{fs.DURATION:.0f}s_rajamouli"
    if args.stills:
        for s in args.stills.split(","):
            Image.frombytes("RGB", (fs.W, fs.H), render(int(float(s) * FPS))).save(
                out / f"{stem}_still_{float(s):05.1f}.png")
        return
    wav = out / f"{stem}_score.wav"
    film.write_wav(wav, epic_score())
    mp4 = out / f"{stem}_9x16.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{fs.W}x{fs.H}",
         "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium",
         "-b:v", "4M", "-maxrate", "6M", "-bufsize", "8M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-af", "loudnorm=I=-15:TP=-1.5", "-movflags", "+faststart", "-shortest", str(mp4)],
        stdin=subprocess.PIPE)
    with Pool(args.workers, initializer=init_fx) as pool:
        for k, buf in enumerate(pool.imap(render, range(int(fs.DURATION * FPS)), chunksize=8)):
            ff.stdin.write(buf)
            if k % (FPS * 15) == 0:
                print(f"  {k / FPS:4.0f}s / {fs.DURATION:.0f}s", flush=True)
    ff.stdin.close()
    ff.wait()
    crop = out / f"{stem}_4x5.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", f"crop={fs.W}:1350:0:{fs.BAR}",
                    "-c:v", "libx264", "-preset", "medium", "-b:v", "3.5M", "-maxrate", "5M", "-bufsize", "7M",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(crop)], check=True)
    print(f"wrote {mp4}\nwrote {crop}")


if __name__ == "__main__":
    main()
