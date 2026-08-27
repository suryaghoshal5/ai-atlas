"""Cluster profiles feed the white paper section 8b table directly, so the two
things that can silently corrupt it are pinned here: the earnings row must be a
survey-weighted worker-level median (not an average of group medians, and not
unweighted), and cluster identity must travel by name — k-means ids permute
whenever the features move."""

import numpy as np
import polars as pl
import pytest

from analysis.typology import name_clusters, profile_clusters, render_table


def workers() -> pl.DataFrame:
    """Two groups per cluster; earnings deliberately arranged so the weighted
    and unweighted medians differ, and so the cluster median differs from the
    mean of its two group medians."""
    rows = []
    spec = {
        # group3: (cluster, alpha, zeta, beta, earnings, weights, grad, female, urban, age)
        "251": (0, 0.60, 0.80, 0.70, [80_000, 90_000, 100_000], [1.0, 1.0, 1.0], 1, 0, 1, 25),
        "241": (0, 0.50, 0.70, 0.60, [40_000, 50_000, 60_000], [9.0, 9.0, 9.0], 1, 1, 1, 30),
        "611": (1, 0.04, 0.06, 0.05, [5_000, 6_000, 7_000], [50.0, 50.0, 50.0], 0, 1, 0, 45),
        "921": (1, 0.02, 0.03, 0.02, [3_000, 4_000, 200_000], [10.0, 10.0, 1.0], 0, 0, 0, 20),
    }
    for g, (c, a, z, b, earn, wts, grad, fem, urb, age) in spec.items():
        for e, w in zip(earn, wts):
            rows.append({"group3": g, "cluster": c, "alpha": a, "zeta": z, "beta": b,
                         "monthly_earnings": float(e), "weight": w,
                         "edu_code": 11 if grad else 5, "sex_code": 2 if fem else 1,
                         "sector_code": 2 if urb else 1, "age": age})
    df = pl.DataFrame(rows)
    return df.drop("cluster"), df.select("group3", "cluster").unique()


def test_cluster_median_is_survey_weighted():
    df, assigned = workers()
    prof = profile_clusters(df, assigned).sort("cluster")
    c0 = df.join(assigned, on="group3").filter(pl.col("cluster") == 0)
    weighted = prof.filter(pl.col("cluster") == 0)["median_earnings_inr"][0]
    unweighted = float(c0["monthly_earnings"].median())
    # 9:1 weights sit on the lower-paid group, so the weighted median must be
    # pulled below the unweighted one — this is the bug the fix addresses
    assert weighted < unweighted
    # and it must equal the median of the population those weights replicate
    expanded = np.repeat(c0["monthly_earnings"].to_numpy(),
                         c0["weight"].to_numpy().astype(int))
    assert weighted == pytest.approx(float(np.median(expanded)))


def test_cluster_median_is_not_an_average_of_group_medians():
    df, assigned = workers()
    prof = profile_clusters(df, assigned).sort("cluster")
    got = prof.filter(pl.col("cluster") == 1)["median_earnings_inr"][0]
    group_medians = [6_000.0, 4_000.0]  # 611 and 921 medians
    assert got != pytest.approx(sum(group_medians) / 2)
    assert got == pytest.approx(6_000.0)  # 611's 150 units of weight dominate


def test_shares_and_wage_bill_are_weighted_and_close():
    df, assigned = workers()
    prof = profile_clusters(df, assigned)
    assert prof["wage_bill_share"].sum() == pytest.approx(1.0)
    for col in ("grad_share", "female_share", "urban_share", "young_share",
                "high_exposure_share"):
        assert prof[col].is_between(0.0, 1.0).all()
    c0 = prof.filter(pl.col("cluster") == 0)
    assert c0["grad_share"][0] == pytest.approx(1.0)
    # 251 (beta .70) is 3 units of weight against 241's 27 — weighted, not counted
    assert c0["high_exposure_share"][0] == pytest.approx(30.0 / 30.0)
    assert c0["female_share"][0] == pytest.approx(27.0 / 30.0)


def test_cluster_names_survive_id_permutation():
    """The whole point of resolving names from the profile: relabelling the
    clusters must not relabel the worlds."""
    prof = pl.DataFrame({
        "cluster": [0, 1, 2, 3, 4],
        "alpha": [0.52, 0.17, 0.13, 0.05, 0.05],
        "e2_share": [0.16, 0.38, 0.07, 0.01, 0.03],
        "grad_share": [0.96, 0.88, 0.74, 0.14, 0.22],
        "urban_share": [0.84, 0.61, 0.60, 0.12, 0.37],
    })
    expected = ["Frontier professionals", "The paperwork layer", "Managers & teachers",
                "Rural agrarian mass", "Urban manual & retail"]
    assert name_clusters(prof) == expected
    shuffled = prof.with_columns(pl.Series("cluster", [4, 2, 0, 3, 1])).sample(
        fraction=1.0, shuffle=True, seed=1)
    by_id = dict(zip(shuffled["cluster"], name_clusters(shuffled)))
    assert [by_id[c] for c in [4, 2, 0, 3, 1]] == expected


def test_non_five_k_falls_back_to_generic_names():
    prof = pl.DataFrame({"cluster": [0, 1, 2], "alpha": [0.5, 0.2, 0.1],
                         "e2_share": [0.1, 0.3, 0.0], "grad_share": [0.9, 0.5, 0.2],
                         "urban_share": [0.8, 0.5, 0.1]})
    assert name_clusters(prof) == ["Cluster 0", "Cluster 1", "Cluster 2"]


def test_render_table_shape():
    df, assigned = workers()
    md = render_table(profile_clusters(df, assigned))
    lines = [ln for ln in md.splitlines() if ln.startswith("|")]
    assert len(lines) == 14                       # header + rule + 12 attribute rows
    assert all(ln.count("|") == 4 for ln in lines)  # 2 clusters + label column
    assert "Median monthly earnings" in md and "₹" in md
    assert "Crop farmers" in md                   # exemplars resolved to labels


def test_write_table_splices_only_the_generated_block(tmp_path, monkeypatch):
    import analysis.typology as t

    wp_dir = tmp_path / "whitepaper"
    wp_dir.mkdir()
    wp = wp_dir / "AI-Exposure-Atlas-WhitePaper.md"
    wp.write_text(f"intro prose\n\n{t.BEGIN_MARK}\nOLD TABLE\n{t.END_MARK}\n\noutro prose\n")
    monkeypatch.setattr(t, "paper_dir", lambda: tmp_path)

    t.write_table("NEW TABLE\n")
    text = wp.read_text()
    assert "OLD TABLE" not in text and "NEW TABLE" in text
    assert text.startswith("intro prose") and text.endswith("outro prose\n")
    assert (wp_dir / "tables" / "typology_clusters_PRELIMINARY.md").read_text() == "NEW TABLE\n"

    t.write_table("NEW TABLE\n")  # regenerating is idempotent, not cumulative
    assert wp.read_text() == text


def test_write_table_leaves_an_unmarked_paper_alone(tmp_path, monkeypatch):
    import analysis.typology as t

    wp_dir = tmp_path / "whitepaper"
    wp_dir.mkdir()
    wp = wp_dir / "AI-Exposure-Atlas-WhitePaper.md"
    wp.write_text("hand-written paper, no markers\n")
    monkeypatch.setattr(t, "paper_dir", lambda: tmp_path)
    t.write_table("NEW TABLE\n")
    assert wp.read_text() == "hand-written paper, no markers\n"
