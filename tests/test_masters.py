"""The master tables are the project's shareable deliverable, so the things
tested here are the ones a reader would take on trust: that every parsed task
survives the join (scored or not), that the PLFS block is survey-weighted, and
that EPFO is never split across NAS heads by an invented allocation."""

import json

import polars as pl
import pytest

import export.masters as m


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A miniature repo: processed parquets, outputs dir, crosswalk config."""
    processed = tmp_path / "processed"
    outputs = tmp_path / "outputs"
    (processed).mkdir()
    (outputs / "tables").mkdir(parents=True)
    (tmp_path / "config").mkdir()

    pl.DataFrame([
        {"nco_code": "2511.0100", "family": "2511", "group3": "251",
         "occupation_title": "Systems analyst", "task_id": "2511.0100-t01",
         "task_text": "Analyses user needs.", "source": "nco_vol2a"},
        {"nco_code": "2511.0100", "family": "2511", "group3": "251",
         "occupation_title": "Systems analyst", "task_id": "2511.0100-t02",
         "task_text": "Documents specifications.", "source": "nco_vol2a"},
        {"nco_code": "6111.0100", "family": "6111", "group3": "611",
         "occupation_title": "Field crop grower", "task_id": "6111.0100-t01",
         "task_text": "Ploughs and sows fields.", "source": "nco_vol2b"},
    ]).write_parquet(processed / "task_statements_full.parquet")

    scores = tmp_path / "scores.parquet"
    pl.DataFrame([  # note: 6111.0100-t01 was never scored
        {"task_id": "2511.0100-t01", "score": "E1", "rubric_version": "0.2-draft",
         "model": "claude-sonnet-4-6", "n_samples": 1, "preliminary": True},
        {"task_id": "2511.0100-t02", "score": "E2", "rubric_version": "0.2-draft",
         "model": "claude-sonnet-4-6", "n_samples": 1, "preliminary": True},
    ]).write_parquet(scores)

    pl.DataFrame([
        {"group3": "251", "n_tasks": 2, "alpha": 0.5, "beta": 0.75, "zeta": 1.0,
         "rubric_version": "0.2-draft", "preliminary": True},
        {"group3": "611", "n_tasks": 8, "alpha": 0.0, "beta": 0.05, "zeta": 0.1,
         "rubric_version": "0.2-draft", "preliminary": True},
    ]).write_parquet(processed / "group3_index_PRELIMINARY.parquet")

    pl.DataFrame([
        {"nco_code": "2511.0100", "n_tasks": 2, "beta": 0.75},
        {"nco_code": "6111.0100", "n_tasks": 4, "beta": 0.05},
    ]).write_parquet(processed / "occupation_index_PRELIMINARY.parquet")

    pl.DataFrame([
        {"group3": "251", "cluster": 2, "name": "Frontier professionals"},
        {"group3": "611", "cluster": 3, "name": "Rural agrarian mass"},
    ]).write_parquet(processed / "occupation_typology_PRELIMINARY.parquet")

    # workers: 251 in NIC 62 (prof. svcs head), 611 in NIC 01 (agriculture).
    # Weights are lopsided so an unweighted median would give a different answer.
    rows = []
    for earn, wt, formal in [(60_000, 1.0, True), (30_000, 9.0, False), (30_000, 9.0, None)]:
        rows.append({"group3": "251", "nic5": "62010", "monthly_earnings": float(earn),
                     "weight": wt, "alpha": 0.5, "beta": 0.75, "zeta": 1.0,
                     "sex_code": 2, "sector_code": 2, "edu_code": 12, "age": 25,
                     "formal_proxy": formal})
    for earn, wt in [(0, 40.0), (6_000, 10.0), (8_000, 5.0)]:
        rows.append({"group3": "611", "nic5": "01110", "monthly_earnings": float(earn),
                     "weight": wt, "alpha": 0.0, "beta": 0.05, "zeta": 0.1,
                     "sex_code": 1, "sector_code": 1, "edu_code": 5, "age": 45,
                     "formal_proxy": False})
    pl.DataFrame(rows).write_parquet(processed / "plfs_exposure_PRELIMINARY.parquet")

    pl.DataFrame([
        {"data_month": mth, "measure": "net_payroll", "age_band": band,
         "industry": ind, "value": val}
        for mth in ("2025-06", "2025-07")
        for ind, band, val in [
            ("IT HEAD", "22-25", 100), ("IT HEAD", ">35", 50),
            ("BUILDING AND CONSTRUCTION INDUSTRY", "18-21", 40),
            ("STRADDLER", "22-25", 9_999),   # spans two NAS heads -> unallocated
        ]
    ]).write_parquet(processed / "epfo_payroll.parquet")

    (tmp_path / "config" / "epfo_nic_crosswalk.yaml").write_text(json.dumps({
        "IT HEAD": {"nic2": ["62", "63"]},                              # prof. svcs
        "BUILDING AND CONSTRUCTION INDUSTRY": {"nic2": ["41", "42"]},   # construction
        "STRADDLER": {"nic2": ["33", "42"]},                            # mfg + construction
    }))

    monkeypatch.setattr(m, "processed_dir", lambda: processed)
    monkeypatch.setattr(m, "outputs_dir", lambda: outputs)
    monkeypatch.setattr(m, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(m, "SCORES", scores)
    return tmp_path


def test_task_master_keeps_unscored_tasks(repo):
    t = m.build_task_master()
    assert t.height == 3
    unscored = t.filter(~pl.col("scored"))
    assert unscored.height == 1 and unscored["task_id"][0] == "6111.0100-t01"
    assert unscored["score"][0] is None
    assert t.filter(pl.col("task_id") == "2511.0100-t02")["exposed"][0] is True


def test_task_master_carries_the_hierarchy_and_index(repo):
    t = m.build_task_master().sort("task_id")
    r = t.filter(pl.col("group3") == "251").row(0, named=True)
    assert (r["division1"], r["sub_division2"], r["family4"]) == ("2", "25", "2511")
    assert r["group3_beta"] == pytest.approx(0.75)
    assert r["occupation_beta"] == pytest.approx(0.75)
    assert r["group3_label"] == "Software developers"
    assert t.filter(pl.col("group3") == "611")["group3_label"][0] == "Crop farmers"


def test_occupation_master_earnings_are_survey_weighted(repo):
    o = m.build_occupation_master(m.load_workers()).sort("group3")
    r251 = o.filter(pl.col("group3") == "251").row(0, named=True)
    # unweighted median of (60k, 30k, 30k) is 30k either way; the mean is the
    # discriminating statistic: unweighted 40k, weighted 31.6k
    assert r251["median_monthly_earnings_inr"] == pytest.approx(30_000)
    assert r251["mean_monthly_earnings_inr"] == pytest.approx(
        (60_000 * 1 + 30_000 * 9 + 30_000 * 9) / 19)
    # zero-earning records are excluded from the median but not from headcount
    r611 = o.filter(pl.col("group3") == "611").row(0, named=True)
    assert r611["median_monthly_earnings_inr"] == pytest.approx(6_000)
    assert r611["earner_share"] == pytest.approx(15 / 55)


def test_occupation_master_shares_and_formality(repo):
    o = m.build_occupation_master(m.load_workers())
    assert o["employment_share"].sum() == pytest.approx(1.0)
    assert o["wage_bill_share"].sum() == pytest.approx(1.0)
    r251 = o.filter(pl.col("group3") == "251").row(0, named=True)
    # formality is a proxy with nulls: the share is over defined records only
    assert r251["formal_proxy_share"] == pytest.approx(1 / 10)
    assert r251["high_exposure"] is True
    assert r251["cluster_name"] == "Frontier professionals"
    assert o.filter(pl.col("group3") == "611")["high_exposure"][0] is False


def test_sector_master_has_every_nas_head_and_maps_workers(repo):
    s, meta = m.build_sector_master(m.load_workers())
    assert s.height == len(m.NAS)
    assert s["gva_share"].sum() == pytest.approx(1.0, abs=1e-6)
    prof = s.filter(pl.col("nas_head") == "Financial, real estate, prof. svcs").row(0, named=True)
    assert prof["workers_m"] == pytest.approx(19 / 1e6)      # NIC 62 -> prof. svcs
    assert prof["mean_beta"] == pytest.approx(0.75)
    agri = s.filter(pl.col("nas_head") == "Agriculture & allied").row(0, named=True)
    assert agri["workers_m"] == pytest.approx(55 / 1e6)      # NIC 01 -> agriculture
    empty = s.filter(pl.col("nas_head") == "Mining & quarrying").row(0, named=True)
    assert empty["workers_m"] is None                        # head kept, no workers
    assert meta["plfs_employment_unmatched_to_any_nas_head"] == pytest.approx(0.0)


def test_epfo_straddling_head_is_unallocated_not_split(repo):
    s, meta = m.build_sector_master(m.load_workers())
    prof = s.filter(pl.col("nas_head") == "Financial, real estate, prof. svcs").row(0, named=True)
    assert prof["epfo_net_payroll_window"] == 300            # (100 + 50) x 2 months
    assert prof["epfo_net_payroll_window_age_le25"] == 200   # the 22-25 band only
    assert prof["epfo_heads_mapped"] == "IT HEAD"
    mfg = s.filter(pl.col("nas_head") == "Manufacturing").row(0, named=True)
    assert mfg["epfo_net_payroll_window"] is None            # straddler not credited
    assert "STRADDLER" in meta["epfo"]["unallocated_heads"]
    assert meta["epfo"]["unallocated_share_of_abs_volume"] > 0.9
    assert meta["epfo"]["window"] == "2025-06..2025-07"


def test_main_writes_all_three_with_metadata(repo):
    m.main()
    tables = repo / "outputs" / "tables"
    for name in ("task_master", "occupation_master", "sector_master"):
        f = tables / f"{name}_PRELIMINARY.csv"
        assert f.exists() and pl.read_csv(f).height > 0
    meta = json.loads((tables / "masters_PRELIMINARY.meta.json").read_text())
    assert meta["task_master"] == {"rows": 3, "scored": 2, "unscored": 1,
                                   "occupations": 2, "groups3": 2}
    assert "PRELIMINARY" in meta["status"]


def test_editorial_label_follows_the_key_not_the_row_order():
    df = pl.DataFrame({"group3": ["611", "251", "999"]})
    assert df.with_columns(m.editorial_label())["group3_label"].to_list() == [
        "Crop farmers", "Software developers", None]
