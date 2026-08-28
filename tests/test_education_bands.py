"""Education bands decide what "graduate" means in every exhibit, so the code
map is pinned here — and the two claim charts are smoke-run on synthetic data,
because neither can be eyeballed without the PLFS extract."""

import re

import polars as pl
import pytest

from atlas_common.education import (BANDS, CODE_LABELS, GRADUATE, GRADUATE_PLUS,
                                    HIGHER_SECONDARY_PLUS, POSTGRADUATE,
                                    band_expr, check_codes)


def test_bands_partition_the_code_set():
    banded = [c for _, codes in BANDS for c in codes]
    assert sorted(banded) == sorted(CODE_LABELS)      # every code, exactly once
    assert len(banded) == len(set(banded))
    assert 9 not in CODE_LABELS                        # the gap the mapping rests on


def test_graduate_and_postgraduate_are_separable():
    assert GRADUATE == [12] and POSTGRADUATE == [13]
    assert GRADUATE_PLUS == [12, 13]
    # the pre-fix definition is kept named, not deleted, so the old series can
    # be reproduced rather than guessed at
    assert HIGHER_SECONDARY_PLUS == [10, 11, 12, 13]
    assert ("Graduate", [12]) in BANDS and ("Postgraduate+", [13]) in BANDS


def test_check_codes_rejects_a_code_set_that_falsifies_the_mapping():
    check_codes([1, 5, 8, 10, 12, 13, None])           # fine
    with pytest.raises(ValueError, match="no 9"):
        check_codes([1, 8, 9, 12])
    with pytest.raises(ValueError, match="unknown"):
        check_codes([1, 14])


def test_band_expr_maps_by_key():
    df = pl.DataFrame({"edu_code": [13, 12, 1, 6]})
    assert df.with_columns(band_expr())["edu_band"].to_list() == [
        "Postgraduate+", "Graduate", "Not literate", "Primary"]


# --------------------------------------------------------------- chart smoke

@pytest.fixture
def workers() -> pl.DataFrame:
    rows = []
    spec = [  # (edu_code, beta, sex_code, sector_code, formal, weight)
        (1, 0.03, 1, 1, False, 300.0), (5, 0.04, 2, 1, False, 200.0),
        (6, 0.05, 1, 1, False, 150.0), (7, 0.06, 2, 1, None, 120.0),
        (8, 0.08, 1, 2, False, 100.0), (10, 0.10, 2, 2, True, 60.0),
        (11, 0.14, 1, 2, True, 40.0), (12, 0.55, 2, 2, True, 30.0),
        (13, 0.61, 1, 2, True, 10.0),
    ]
    for edu, beta, sex, sect, formal, wt in spec:
        rows.append({"edu_code": edu, "beta": beta, "sex_code": sex,
                     "sector_code": sect, "formal_proxy": formal, "weight": wt,
                     "group3": "251", "div": "2", "monthly_earnings": 20_000.0})
    return pl.DataFrame(rows)


def test_education_chart_runs_and_records_both_series(tmp_path, monkeypatch, workers):
    import insights.insight_atlas_claims as c

    monkeypatch.setattr(c, "OUT", tmp_path)
    monkeypatch.setattr(c, "PROV", [])
    c.apply_style()
    c.chart_education(workers)

    assert (tmp_path / "insight_education.png").exists()
    prov = c.PROV[0]
    assert "Graduate=" in prov and "Postgraduate+=" in prov
    assert "labour-force shares %" in prov
    # the share series is a share of ALL employed workers and must total 100
    section = prov.split("labour-force shares %: ")[1].split("\n")[0]
    shares = [float(v) for v in re.findall(r"=([\d.]+)", section)]
    assert len(shares) == 9
    # 9 values each rounded to one decimal in the provenance line
    assert sum(shares) == pytest.approx(100.0, abs=0.5)


def test_gender_chart_computes_the_one_in_n_incidence(tmp_path, monkeypatch, workers):
    import insights.insight_atlas_claims as c

    monkeypatch.setattr(c, "OUT", tmp_path)
    monkeypatch.setattr(c, "PROV", [])
    c.apply_style()
    c.chart_gender(workers)

    assert (tmp_path / "insight_gender_flip.png").exists()
    prov = c.PROV[0]
    assert "share in beta>=0.5 %" in prov          # the number the caption quotes
    assert "mean beta" in prov
    # organised women here: 60 + 30 units, 30 of them at beta .42+ -> 33%
    organised = prov.split("organised M=")[-1]
    assert "F=33.3" in organised
