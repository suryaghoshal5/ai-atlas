"""Agreement statistics and sheet invariants for the human-validation round."""

from analysis.validation_kappa import cohens_kappa, fleiss_kappa, majority


def test_cohens_kappa_known_values():
    assert cohens_kappa(["E0", "E1"] * 5, ["E0", "E1"] * 5) == 1.0
    # perfect disagreement on a balanced pair -> -1
    assert cohens_kappa(["E0", "E1"] * 5, ["E1", "E0"] * 5) == -1.0
    # textbook 2x2: a=20 b=5 c=10 d=15 -> po=.7, pe=.5 -> kappa .4
    a = ["E0"] * 25 + ["E1"] * 25
    b = ["E0"] * 20 + ["E1"] * 5 + ["E0"] * 10 + ["E1"] * 15
    assert cohens_kappa(a, b) == 0.4
    assert cohens_kappa([], []) is None


def test_fleiss_kappa_agreement_bounds():
    assert fleiss_kappa([["E0"] * 3, ["E1"] * 3, ["E2"] * 3]) == 1.0
    assert fleiss_kappa([]) is None
    k = fleiss_kappa([["E0", "E1", "E2"], ["E1", "E2", "E0"], ["E2", "E0", "E1"]])
    assert k is not None and k < 0


def test_majority_and_ties():
    assert majority(["E0", "E0", "E1"]) == "E0"
    assert majority(["E0", "E1", "E2"]) is None
    assert majority(["E1"]) == "E1"
