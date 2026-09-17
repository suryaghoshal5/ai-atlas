"""Agreement statistics for the human-validation sheet (Golden Rule 4).

Reads outputs/validation/rating_sheet_v1.csv (filled) and the key, and writes
outputs/validation/validation_kappa_report.json with:
    * Cohen's kappa, each rater vs the LLM label, on the rows that rater scored;
    * Cohen's kappa, majority human label vs LLM (ties -> excluded, counted);
    * Fleiss' kappa across the human raters on rows all of them scored;
    * per-stratum percent agreement (majority vs LLM);
    * counts of blanks, NA rows, R-03 / R-04 notes.
The gate is config validation.min_kappa on the majority-vs-LLM Cohen's kappa
(the statistic the pilot rounds used). Below it: STOP, no index build is final.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

import polars as pl

from atlas_common import load_config, outputs_dir

OUT = outputs_dir() / "validation"
LABELS = ("E0", "E1", "E2")


def cohens_kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] / n * cb[k] / n for k in LABELS)
    return None if pe == 1 else round((po - pe) / (1 - pe), 4)


def fleiss_kappa(rows: list[list[str]]) -> float | None:
    """rows: one list of labels per item, all of equal length (n raters)."""
    if not rows:
        return None
    n = len(rows[0])
    if n < 2:
        return None
    p_i, totals = [], Counter()
    for r in rows:
        c = Counter(r)
        totals.update(c)
        p_i.append((sum(v * v for v in c.values()) - n) / (n * (n - 1)))
    p_bar = sum(p_i) / len(rows)
    tot = n * len(rows)
    pe = sum((totals[k] / tot) ** 2 for k in LABELS)
    return None if pe == 1 else round((p_bar - pe) / (1 - pe), 4)


def majority(labels: list[str]) -> str | None:
    c = Counter(labels).most_common()
    if not c or (len(c) > 1 and c[0][1] == c[1][1]):
        return None
    return c[0][0]


def main() -> None:
    cfg = load_config()
    sheet = pl.read_csv(OUT / "rating_sheet_v1.csv", infer_schema_length=0)
    key = pl.read_csv(OUT / "rating_sheet_v1_key.csv", infer_schema_length=0)
    df = sheet.join(key.select("task_id", "llm_label", "stratum"), on="task_id", how="left")
    rcols = [c for c in df.columns if c.startswith("rating_")]
    ncols = [c for c in df.columns if c.startswith("notes_")]

    def clean(v: str | None) -> str | None:
        v = (v or "").strip().upper()
        return v if v in LABELS or v == "NA" else None

    rows = df.to_dicts()
    report: dict = {"computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "n_rows": len(rows), "raters": {}, "gate_stat": "majority_vs_llm_cohens_kappa"}
    # per rater vs LLM
    for rc in rcols:
        a, b, blanks, na = [], [], 0, 0
        for r in rows:
            v = clean(r[rc])
            if v is None:
                blanks += 1
            elif v == "NA":
                na += 1
            elif r["llm_label"] in LABELS:
                a.append(v)
                b.append(r["llm_label"])
        report["raters"][rc] = {"n_scored_vs_llm": len(a), "blank": blanks, "na": na,
                                "percent_agreement": round(sum(x == y for x, y in zip(a, b)) / len(a), 4) if a else None,
                                "cohens_kappa_vs_llm": cohens_kappa(a, b),
                                "distribution": dict(Counter(a))}
    # majority vs LLM, Fleiss across raters, per stratum
    maj_a, maj_b, ties, strata = [], [], 0, {}
    fleiss_rows = []
    for r in rows:
        vals = [clean(r[rc]) for rc in rcols]
        human = [v for v in vals if v in LABELS]
        if len(human) == len(rcols):
            fleiss_rows.append(human)
        if not human:
            continue
        m = majority(human)
        if m is None:
            ties += 1
            continue
        if r["llm_label"] in LABELS:
            maj_a.append(m)
            maj_b.append(r["llm_label"])
            s = strata.setdefault(r["stratum"], [0, 0])
            s[0] += 1
            s[1] += int(m == r["llm_label"])
    report["majority_vs_llm"] = {"n": len(maj_a), "ties_excluded": ties,
                                 "percent_agreement": round(sum(x == y for x, y in zip(maj_a, maj_b)) / len(maj_a), 4) if maj_a else None,
                                 "cohens_kappa": cohens_kappa(maj_a, maj_b)}
    report["fleiss_kappa_humans"] = {"n_items_all_raters": len(fleiss_rows), "kappa": fleiss_kappa(fleiss_rows)}
    report["per_stratum_agreement"] = {k: {"n": v[0], "agree": v[1], "pct": round(v[1] / v[0], 4)} for k, v in strata.items()}
    flags = Counter()
    for r in rows:
        for nc in ncols:
            for tag in ("R-03", "R-04", "R-05"):
                if tag in (r[nc] or ""):
                    flags[tag] += 1
    report["note_flags"] = dict(flags)
    k = report["majority_vs_llm"]["cohens_kappa"]
    report["gate"] = ("not computable (no complete ratings yet)" if k is None else
                      f"PASS (kappa {k} >= {cfg['validation']['min_kappa']})" if k >= cfg["validation"]["min_kappa"]
                      else f"FAIL (STOP: kappa {k} < {cfg['validation']['min_kappa']}; revise rubric, do not finalise index)")
    (OUT / "validation_kappa_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
