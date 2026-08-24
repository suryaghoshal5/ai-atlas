"""Parse NCO-2015 Vol II-A/B occupation descriptions into task statements.

Entry anatomy in the PDFs (born-digital, linear extraction):

    1324.1100
    Traffic Officer, Air Service/Traffic Controller
    <description: role sentence + duty sentences ...>
    ISCO 08 Unit Group Details: Code 1324 Title ...

Codes are 4-digit family + 4-digit occupation suffix. PLFS merges at 3-digit
(group = first 3 digits of the family), so every entry carries `group3`.

Raw PDFs are read-only inputs; outputs go to data/processed/ (Golden Rule 6).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
from pypdf import PdfReader

from atlas_common import processed_dir, raw_dir

CODE_RE = re.compile(r"\b(\d{4}\.\d{4})\b")
ISCO_CUT_RE = re.compile(r"ISCO\s*08\s*Unit\s*Group\s*Details.*", re.DOTALL)
# Vol II-B entries end with skill-certification metadata, not task content
QP_CUT_RE = re.compile(r"Qualification\s*Pack\s*Details.*", re.DOTALL)
# page furniture lines to drop before joining
FURNITURE_RE = re.compile(
    r"^(VOLUME II ?[AB]|National Classification of Occupations.*|Division \d+|\d{1,3})\s*$"
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;])\s+(?=[A-Z])")


def _clean(text: str) -> str:
    # page furniture that survives line filtering when merged into a content line
    text = re.sub(r"VOLUME II ?[AB](\s+\d{1,3})?", " ", text)
    text = re.sub(r"National Classification of Occupations\s*[–-]\s*2015(\s+Division \d)?", " ", text)
    # rejoin words split across line breaks by the extractor: "stand -by" -> "stand-by"
    text = re.sub(r"(\w)\s+-\s*(\w)", r"\1-\2", text)
    text = re.sub(r"(\w)\s*-\s+(\w)", r"\1-\2", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _dedupe_title(title: str) -> str:
    """Vol II prints the heading and the running title back to back; collapse a
    repeated leading phrase ("Butler Butler" -> "Butler")."""
    def norm(w: str) -> str:
        return w.lower().rstrip(",;").rstrip("s")

    words = title.split()
    for n in range(min(6, len(words) // 2), 0, -1):
        if [norm(w) for w in words[:n]] == [norm(w) for w in words[n : 2 * n]]:
            title = " ".join(words[n:])
            break
    title = re.sub(r"\s+([;,])", r"\1", title)
    return title.strip(" ;,")


def extract_volume_text(pdf_path: Path) -> str:
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        lines = (page.extract_text() or "").splitlines()
        pages.append("\n".join(l for l in lines if not FURNITURE_RE.match(l.strip())))
    return "\n".join(pages)


def parse_entries(text: str, source: str) -> list[dict]:
    """Split volume text on occupation codes; each segment is title + description."""
    parts = CODE_RE.split(text)
    entries = []
    # parts = [preamble, code, segment, code, segment, ...]
    for code, segment in zip(parts[1::2], parts[2::2]):
        segment = ISCO_CUT_RE.sub("", segment)
        segment = QP_CUT_RE.sub("", segment)
        lines = [l.strip() for l in segment.splitlines() if l.strip()]
        if not lines:
            continue
        # title: leading lines up to where the description begins. The description
        # always re-opens with one of the title's aliases as its subject, so stop
        # absorbing as soon as a line opens with a word pair already seen in the
        # title collected so far.
        title_lines: list[str] = []
        rest_idx = 0
        for i, line in enumerate(lines[:3]):
            opening = " ".join(_clean(line).split()[:2]).lower()
            seen = _clean(" ".join(title_lines)).lower()
            if "." in line or (title_lines and opening and opening in seen):
                break
            if sum(len(t) for t in title_lines) > 90:
                break
            title_lines.append(line)
            rest_idx = i + 1
        title = _clean(" ".join(title_lines))
        description = _clean(" ".join(lines[rest_idx:]))
        # extractor sometimes merges the description start onto the title line;
        # descriptions open with a 3rd-person-singular verb ("records ...",
        # "supervises ..."), while title connectors ("and", "cum", "of") never
        # end in -s — split the title at the first such token
        tokens = title.split()
        for i, tok in enumerate(tokens):
            w = tok.strip(",;")
            nxt = tokens[i + 1].strip(",;") if i + 1 < len(tokens) else ""
            if re.fullmatch(r"[a-z]{3,}s", w):
                # description verb merged onto the title line
                description = (" ".join(tokens[i:]) + " " + description).strip()
                title = _clean(" ".join(tokens[:i])).rstrip(",;")
                break
            if w.islower() and nxt.islower() and re.fullmatch(r"[a-z]{4,}s", w + nxt):
                # same, but the verb itself was split mid-word ("assi sts")
                description = (w + nxt + " " + " ".join(tokens[i + 2:]) + " " + description).strip()
                title = _clean(" ".join(tokens[:i])).rstrip(",;")
                break
        title = _dedupe_title(title)
        if not title or len(description) < 40:
            continue
        entries.append(
            {
                "nco_code": code,
                "family": code[:4],
                "group3": code[:3],
                "occupation_title": title,
                "description": description,
                "source": source,
            }
        )
    return entries


def parse_all() -> pl.DataFrame:
    nco_raw = raw_dir() / "nco"
    frames = []
    for pdf, src in [
        ("NCO-2015_Vol_II-A.pdf", "nco_vol2a"),
        ("NCO-2015_Vol_II-B.pdf", "nco_vol2b"),
    ]:
        text = extract_volume_text(nco_raw / pdf)
        frames.extend(parse_entries(text, src))
    df = pl.DataFrame(frames)
    # a code can appear once as a header and again in cross-references; keep the
    # longest description per code
    df = (
        df.sort("description", descending=True)
        .group_by("nco_code", maintain_order=True)
        .first()
        .sort("nco_code")
    )
    return df


def split_tasks(description: str, title: str) -> list[str]:
    """Sentence-split a description into task statements.

    The first sentence usually opens with one of the title's aliases as subject
    ("Traffic Officer, Air Service supervises ..."); strip that subject so
    every task statement starts with the verb phrase.
    """
    aliases = sorted(
        (a.strip() for part in title.split("/") for a in part.split(";") if a.strip()),
        key=len,
        reverse=True,
    )
    tasks = []
    for sent in SENTENCE_SPLIT_RE.split(description):
        sent = sent.strip().rstrip(";").strip()
        for alias in aliases:
            if sent.lower().startswith(alias.lower()):
                sent = sent[len(alias):].lstrip(" ,")
                sent = sent[:1].upper() + sent[1:]
                break
        if len(sent) >= 15:
            tasks.append(sent if sent.endswith(".") else sent + ".")
    return tasks


def main() -> None:
    out_dir = processed_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    df = parse_all()
    path = out_dir / "nco_entries_vol2.parquet"
    df.write_parquet(path)
    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "n_entries": df.height,
        "n_families": df["family"].n_unique(),
        "n_groups3": df["group3"].n_unique(),
        "inputs": ["data/raw/nco/NCO-2015_Vol_II-A.pdf", "data/raw/nco/NCO-2015_Vol_II-B.pdf"],
    }
    (out_dir / "nco_entries_vol2.meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
