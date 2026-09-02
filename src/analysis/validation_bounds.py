"""Validation bounding exercise (PRELIMINARY per D6).

How much can the unresolved human-vs-LLM disagreement move beta? Uses the
round-1 pilot confusion matrix (383 usable pairs; outputs/pilot/
pilot_confusion_matrix.csv) and reports:

  1. flip composition (E0<->E1 full-weight vs E1<->E2 / E0<->E2 half-weight)
  2. pilot mean beta under LLM labels vs full substitution of human labels
  3. one-directional adversarial bounds (every disagreement resolved to the
     beta-minimising / beta-maximising label) - the extreme worst case

Feeds the research-sample appendix. Output:
outputs/tables/validation_bounds_PRELIMINARY.json
"""

from __future__ import annotations

import csv
import json

from atlas_common import outputs_dir

BW = {"E0": 0.0, "E1": 1.0, "E2": 0.5}  # beta task weight


def main() -> None:
    cm: dict[tuple[str, str], int] = {}
    with open(outputs_dir() / "pilot" / "pilot_confusion_matrix.csv") as f:
        for row in csv.DictReader(f):
            h = row["human"]
            for lab in ["E0", "E1", "E2"]:
                cm[(h, lab)] = int(row[f"llm_{lab}"])

    n = sum(cm.values())
    n_dis = sum(v for (h, l), v in cm.items() if h != l)
    pair_ct = lambda a, b: cm[(a, b)] + cm[(b, a)]

    llm_beta = sum(v * BW[l] for (h, l), v in cm.items()) / n
    hum_beta = sum(v * BW[h] for (h, l), v in cm.items()) / n
    lo = sum(v * (min(BW[h], BW[l]) if h != l else BW[l]) for (h, l), v in cm.items()) / n
    hi = sum(v * (max(BW[h], BW[l]) if h != l else BW[l]) for (h, l), v in cm.items()) / n

    out = {
        "status": "PRELIMINARY per D6; round-1 pilot confusion matrix, 383 pairs",
        "n_pairs": n,
        "n_disagreements": n_dis,
        "disagreement_rate_pct": round(n_dis / n * 100, 1),
        "flips": {
            "E0<->E1_full_weight": {"n": pair_ct("E0", "E1"),
                                    "share_of_tasks_pct": round(pair_ct("E0", "E1") / n * 100, 1),
                                    "direction_split": {"human_E0_llm_E1": cm[("E0", "E1")],
                                                        "human_E1_llm_E0": cm[("E1", "E0")]}},
            "E1<->E2_half_weight": {"n": pair_ct("E1", "E2"),
                                    "share_of_tasks_pct": round(pair_ct("E1", "E2") / n * 100, 1)},
            "E0<->E2_half_weight": {"n": pair_ct("E0", "E2"),
                                    "share_of_tasks_pct": round(pair_ct("E0", "E2") / n * 100, 1)},
        },
        "pilot_mean_beta_llm": round(llm_beta, 3),
        "pilot_mean_beta_human_substituted": round(hum_beta, 3),
        "substitution_delta": round(hum_beta - llm_beta, 3),
        "substitution_delta_relative_pct": round((hum_beta - llm_beta) / llm_beta * 100, 1),
        "adversarial_bound": {"low": round(lo, 3), "high": round(hi, 3),
                              "relative_pct": [round((lo - llm_beta) / llm_beta * 100, 0),
                                               round((hi - llm_beta) / llm_beta * 100, 0)]},
        "reading": ("Full substitution of human for machine labels moves pilot beta by "
                    "-0.009 (5% relative): directional flips nearly cancel (12 human-E0/"
                    "llm-E1 vs 10 human-E1/llm-E0). The one-directional adversarial bound "
                    "is wide but assumes every disagreement resolves the same way, which "
                    "the observed human labels contradict."),
    }
    (outputs_dir() / "tables" / "validation_bounds_PRELIMINARY.json").write_text(
        json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
