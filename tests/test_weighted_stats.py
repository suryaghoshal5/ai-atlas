"""The survey-weighted median must (a) reduce to the unweighted one when the
design is flat and (b) reproduce the median of the population the weights
represent. Both are checked directly — a weighted statistic that silently
ignores its weights is the failure mode this guards."""

import numpy as np
import pytest

from atlas_common.stats import weighted_median, weighted_quantile


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8, 33, 100])
def test_equal_weights_match_numpy_median(n):
    rng = np.random.default_rng(42)
    v = rng.normal(size=n)
    assert weighted_median(v, np.ones(n)) == pytest.approx(float(np.median(v)))


def test_integer_weights_match_expanded_population():
    v = np.array([10.0, 20.0, 30.0, 40.0])
    w = np.array([1.0, 5.0, 1.0, 1.0])
    expanded = np.repeat(v, w.astype(int))
    assert weighted_median(v, w) == pytest.approx(float(np.median(expanded)))


def test_weights_actually_move_the_answer():
    # PLFS-shaped: a handful of high earners sampled heavily, the mass poor
    v = np.array([5_000.0, 6_000.0, 7_000.0, 80_000.0, 90_000.0])
    heavy_top = weighted_median(v, np.array([1.0, 1.0, 1.0, 20.0, 20.0]))
    heavy_bottom = weighted_median(v, np.array([20.0, 20.0, 20.0, 1.0, 1.0]))
    assert heavy_top > np.median(v) > heavy_bottom


def test_scale_invariant_in_weights():
    v = np.array([1.0, 4.0, 9.0, 16.0])
    w = np.array([3.0, 1.0, 4.0, 2.0])
    assert weighted_median(v, w) == pytest.approx(weighted_median(v, w * 1000.0))


def test_zero_weights_drop_out():
    v = np.array([1.0, 2.0, 3.0, 999.0])
    w = np.array([1.0, 1.0, 1.0, 0.0])
    assert weighted_median(v, w) == pytest.approx(2.0)


def test_unsorted_input_ok():
    v = np.array([30.0, 10.0, 20.0])
    w = np.array([1.0, 1.0, 1.0])
    assert weighted_median(v, w) == pytest.approx(20.0)


def test_quantiles_are_monotone():
    rng = np.random.default_rng(7)
    v, w = rng.normal(size=200), rng.uniform(0.1, 5, size=200)
    qs = [weighted_quantile(v, w, q) for q in (0.1, 0.25, 0.5, 0.75, 0.9)]
    assert qs == sorted(qs)
    assert weighted_quantile(v, w, 0.0) == pytest.approx(v.min())
    assert weighted_quantile(v, w, 1.0) == pytest.approx(v.max())


@pytest.mark.parametrize("v,w,q", [
    ([1.0, 2.0], [1.0, -1.0], 0.5),      # negative survey weight
    ([1.0, np.nan], [1.0, 1.0], 0.5),    # NaN value
    ([1.0, 2.0], [1.0], 0.5),            # shape mismatch
    ([], [], 0.5),                       # empty
    ([1.0, 2.0], [0.0, 0.0], 0.5),       # no positive weight
    ([1.0, 2.0], [1.0, 1.0], 1.5),       # q out of range
])
def test_bad_input_raises(v, w, q):
    with pytest.raises(ValueError):
        weighted_quantile(v, w, q)
