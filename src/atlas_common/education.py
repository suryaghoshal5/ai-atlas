"""PLFS general education codes (b4q8), and the bands built on them.

The NSS code set is NOT contiguous — there is no 09, and that gap is the tell
that the ladder runs:

    01  not literate
    02  literate without formal schooling: EGS/NFEC/AEC
    03  literate without formal schooling: TLC
    04  literate without formal schooling: others
    05  literate: below primary
    06  primary
    07  middle
    08  secondary
    10  higher secondary
    11  diploma/certificate course
    12  graduate
    13  postgraduate and above

CHECK BEFORE PUBLICATION: this mapping is read off the NSS/PLFS standard code
list, not off docs/Data_LayoutPLFS_2023-24.xlsx (which is not in the repo — raw
data is read-only and uncommitted). It replaces an earlier ad-hoc banding that
treated 06-07 as "secondary/HS", 08 as "diploma" and 10-13 as "graduate+",
which is shifted about two rungs down this ladder and cannot be reconciled with
the missing 09. If the layout workbook contradicts the list above, this file is
the single place to fix it — everything downstream reads these constants.

`check_codes` fails loudly if the data contains a 9 (which would falsify the
whole mapping) or a code outside the set.
"""

from __future__ import annotations

import polars as pl

CODE_LABELS = {
    1: "Not literate",
    2: "Literate without formal schooling: EGS/NFEC/AEC",
    3: "Literate without formal schooling: TLC",
    4: "Literate without formal schooling: others",
    5: "Literate: below primary",
    6: "Primary",
    7: "Middle",
    8: "Secondary",
    10: "Higher secondary",
    11: "Diploma/certificate course",
    12: "Graduate",
    13: "Postgraduate and above",
}

# Reporting bands: the four "literate without formal schooling / below primary"
# codes collapse into one rung; everything from secondary up stays separate, so
# the graduate and postgraduate rungs can be read on their own.
BANDS: list[tuple[str, list[int]]] = [
    ("Not literate", [1]),
    ("Below primary", [2, 3, 4, 5]),
    ("Primary", [6]),
    ("Middle", [7]),
    ("Secondary", [8]),
    ("Higher secondary", [10]),
    ("Diploma/certificate", [11]),
    ("Graduate", [12]),
    ("Postgraduate+", [13]),
]

GRADUATE = [12]
POSTGRADUATE = [13]
GRADUATE_PLUS = [12, 13]
# what the pre-fix `grad_share` actually measured — kept named so the old
# series can be reproduced for comparison instead of guessed at
HIGHER_SECONDARY_PLUS = [10, 11, 12, 13]


def check_codes(codes) -> None:
    """Fail loudly if the observed codes contradict the mapping above."""
    seen = {int(c) for c in codes if c is not None}
    if 9 in seen:
        raise ValueError(
            "education code 9 is present, but the NSS ladder in "
            "atlas_common.education has no 9 — the code set is not the one "
            "assumed. Re-read docs/Data_LayoutPLFS_2023-24.xlsx before using "
            "any education cut."
        )
    unknown = sorted(seen - set(CODE_LABELS))
    if unknown:
        raise ValueError(f"unknown education codes {unknown}; expected {sorted(CODE_LABELS)}")


def band_expr(col: str = "edu_code") -> pl.Expr:
    """Map education codes to reporting bands, by key."""
    mapping = {code: label for label, codes in BANDS for code in codes}
    return pl.col(col).replace_strict(mapping, default=None, return_dtype=pl.Utf8).alias("edu_band")


BAND_ORDER = [label for label, _ in BANDS]
