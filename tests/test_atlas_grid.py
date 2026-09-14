"""Square allocation for the atlas grid must be exact and deterministic."""

from insights.atlas_grid import largest_remainder, sector_of


def test_largest_remainder_sums_to_total():
    w = [193.9, 116.7, 149.9]
    out = largest_remainder(w, 463)
    assert sum(out) == 463
    assert out == [195, 117, 151]


def test_largest_remainder_zero_weight_gets_nothing():
    assert largest_remainder([0.0, 5.0, 0.0], 7) == [0, 7, 0]
    assert largest_remainder([1.0, 1.0], 0) == [0, 0]
    assert largest_remainder([], 5) == []


def test_ties_broken_by_weight_then_index():
    # quotas 1.5 / 1.5 with 3 squares: the heavier of two equal fractions wins
    assert largest_remainder([1.5, 1.5], 3) in ([2, 1], [1, 2])
    assert sum(largest_remainder([0.3] * 10, 3)) == 3


def test_sector_of_boundaries():
    assert sector_of(1) == "agriculture"
    assert sector_of(3) == "agriculture"
    assert sector_of(5) == "industry"
    assert sector_of(43) == "industry"
    assert sector_of(45) == "services"
    assert sector_of(99) == "services"
    assert sector_of(4) is None and sector_of(44) is None and sector_of(None) is None
