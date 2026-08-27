"""Survey-weighted statistics.

PLFS unit records are only workforce-representative once the multiplier is
applied (weight = mult/no_qtr, see merge.plfs), so an unweighted median over
unit records is a median of the *sample*, not of the workforce. Any statistic
reported for a segment — occupation group, cluster, sector, state — goes
through here.
"""

from __future__ import annotations

import numpy as np


def weighted_quantile(values, weights, q: float) -> float:
    """Quantile q of the weighted empirical distribution of `values`.

    The classic weighted-order-statistic definition: sort by value, walk the
    cumulative weight, and take the first observation whose cumulative weight
    reaches q * W — averaging the two straddling observations when the cut
    falls exactly on a boundary. Two properties this buys, both tested:

      * with equal weights it returns exactly numpy's `median` (odd n and the
        even-n average alike), so the weighted path degenerates to the
        unweighted one when the design is flat;
      * with integer weights it returns the median of the population those
        weights replicate — which is what a survey multiplier means. An
        interpolated (piecewise-linear CDF) quantile does NOT have this
        property, and on lumpy earnings data it also invents values nobody
        reported; that is why this is a step function.

    Zero-weight rows drop out. NaNs raise rather than propagate — a NaN here
    means an upstream fill that should have been made explicit.
    """
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    if v.ndim != 1 or v.shape != w.shape:
        raise ValueError(f"values {v.shape} and weights {w.shape} must be matching 1-D arrays")
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"q must be in [0, 1], got {q}")
    if np.isnan(v).any() or np.isnan(w).any():
        raise ValueError("NaN in values or weights — fill explicitly upstream")
    if (w < 0).any():
        raise ValueError("negative survey weights")
    keep = w > 0
    v, w = v[keep], w[keep]
    if v.size == 0:
        raise ValueError("no positive-weight observations")
    order = np.argsort(v, kind="stable")
    v, w = v[order], w[order]
    cum = np.cumsum(w)
    target = q * cum[-1]
    i = min(int(np.searchsorted(cum, target, side="left")), v.size - 1)
    on_boundary = abs(cum[i] - target) <= 1e-9 * cum[-1]
    if on_boundary and i < v.size - 1:
        return float((v[i] + v[i + 1]) / 2.0)
    return float(v[i])


def weighted_median(values, weights) -> float:
    return weighted_quantile(values, weights, 0.5)
