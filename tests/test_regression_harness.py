"""Regression harness (Golden Rule 8): every table in outputs/tables/ is compared
against its golden copy in tests/golden/tables/. A sign/significance flip after a
code change surfaces here as a diff -> STOP, bisect, report before commit.

Workflow:
  1. `make results` regenerates outputs/tables/*.csv
  2. this test diffs them against tests/golden/tables/
  3. intentional result changes are promoted with scripts/promote_golden.py
     (to be added) after explicit review — never by editing golden files by hand.
"""

import filecmp
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "tests" / "golden" / "tables"
OUTPUTS = REPO / "outputs" / "tables"


def golden_files():
    if not GOLDEN.exists():
        return []
    return sorted(p.name for p in GOLDEN.glob("*.csv"))


@pytest.mark.parametrize("name", golden_files() or ["__no_golden_yet__"])
def test_output_matches_golden(name):
    if name == "__no_golden_yet__":
        pytest.skip("No golden outputs yet (pre-first-results); harness armed but empty.")
    out = OUTPUTS / name
    assert out.exists(), f"golden table {name} has no regenerated counterpart in outputs/tables/"
    assert filecmp.cmp(GOLDEN / name, out, shallow=False), (
        f"REGRESSION: {name} differs from golden. STOP — bisect and report before commit."
    )
