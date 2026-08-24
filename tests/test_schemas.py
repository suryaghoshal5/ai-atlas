"""Schema sanity: each pandera schema accepts a valid row and rejects a bad one.
These tests pin the contract that ingest parsers must satisfy."""

import polars as pl
import pandera.errors
import pytest

from atlas_common import schemas


def _validate(schema, df):
    return schema.validate(df, lazy=True)


def test_task_statements_accepts_valid_row():
    df = pl.DataFrame(
        {
            "nco_code": ["7412.0100"],
            "group3": ["741"],
            "occupation_title": ["Electrician, General"],
            "task_id": ["7412.0100-t01"],
            "task_text": ["Installs and repairs wiring in residential buildings"],
            "source": ["nco_vol2b"],
        }
    )
    _validate(schemas.task_statements, df)


def test_task_statements_rejects_bad_nco_code():
    df = pl.DataFrame(
        {
            "nco_code": ["74X2"],
            "group3": ["741"],
            "occupation_title": ["Electrician, General"],
            "task_id": ["t01"],
            "task_text": ["Installs and repairs wiring in residential buildings"],
            "source": ["nco_vol2b"],
        }
    )
    with pytest.raises(pandera.errors.SchemaErrors):
        _validate(schemas.task_statements, df)


def test_task_scores_rejects_invalid_score():
    df = pl.DataFrame(
        {
            "task_id": ["t01"],
            "rubric_version": ["0.1-draft"],
            "model": ["claude-sonnet-4-6"],
            "score": ["E3"],
            "votes_e0": [0],
            "votes_e1": [2],
            "votes_e2": [1],
            "tie_escalated": [False],
            "scored_at": ["2026-07-17T00:00:00+00:00"],
        }
    )
    with pytest.raises(pandera.errors.SchemaErrors):
        _validate(schemas.task_scores, df)


def test_occupation_index_bounds():
    df = pl.DataFrame(
        {
            "nco_code": ["7412"],
            "occupation_title": ["Electrician, General"],
            "n_tasks": [12],
            "variant": ["E1"],
            "alpha": [0.25],
            "beta": [0.4],
            "zeta": [1.2],  # out of range
            "rubric_version": ["0.1-draft"],
        }
    )
    with pytest.raises(pandera.errors.SchemaErrors):
        _validate(schemas.occupation_index, df)
