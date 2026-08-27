"""Pandera schemas for every processed table in the pipeline.

Ingest parsers must validate against these before writing parquet
(Golden Rule: hard fail with row samples, never coerce silently).
Schemas are drafts until the corresponding raw data has been inspected;
tighten them at ingest time, never loosen to make bad data pass.
"""

from __future__ import annotations

import pandera.polars as pa
from pandera.polars import Column

# NCO-2015 task statements parsed from Vol II-A/B (plus flagged posting-derived
# augmentations for the E1+ variant). nco_code is the full 8-digit occupation
# code (4-digit family + 4-digit suffix); group3 is the 3-digit group PLFS
# merges on.
task_statements = pa.DataFrameSchema(
    {
        "nco_code": Column(str, pa.Check.str_matches(r"^\d{4}\.\d{4}$")),
        "group3": Column(str, pa.Check.str_matches(r"^\d{3}$")),
        "occupation_title": Column(str),
        "task_id": Column(str, unique=True),
        "task_text": Column(str, pa.Check.str_length(min_value=10)),
        "source": Column(str, pa.Check.isin(["nco_vol2a", "nco_vol2b", "posting_derived"])),
    },
    strict=True,
    coerce=False,
)

# The 50-occupation pilot uses the same contract.
pilot_tasks = task_statements

# One row per task per rubric version: majority-vote LLM score with provenance.
task_scores = pa.DataFrameSchema(
    {
        "task_id": Column(str),
        "rubric_version": Column(str),
        "model": Column(str),
        # "TIE" rows carry no majority verdict and are escalated to human review
        "score": Column(str, pa.Check.isin(["E0", "E1", "E2", "TIE"])),
        "votes_e0": Column(int, pa.Check.ge(0)),
        "votes_e1": Column(int, pa.Check.ge(0)),
        "votes_e2": Column(int, pa.Check.ge(0)),
        "tie_escalated": Column(bool),
        "scored_at": Column(str),  # ISO timestamp
    },
    strict=True,
)

# Occupation-level exposure index (E1 core and E1+ augmented, three aggregations).
occupation_index = pa.DataFrameSchema(
    {
        "nco_code": Column(str),
        "occupation_title": Column(str),
        "n_tasks": Column(int, pa.Check.gt(0)),
        "variant": Column(str, pa.Check.isin(["E1", "E1plus"])),
        "alpha": Column(float, pa.Check.in_range(0, 1)),  # share E1
        "beta": Column(float, pa.Check.in_range(0, 1)),   # E1 + 0.5*E2
        "zeta": Column(float, pa.Check.in_range(0, 1)),   # E1 + E2
        "rubric_version": Column(str),
        # D6: True until human validation clears; preliminary rows never enter the paper
        "preliminary": Column(bool),
    },
    strict=True,
)

# PLFS worker-level records after merging the index (survey-weighted analysis base).
plfs_workers = pa.DataFrameSchema(
    {
        "person_id": Column(str, unique=True),
        "survey_year": Column(str, pa.Check.isin(["2022-23", "2023-24"])),
        "weight": Column(float, pa.Check.gt(0)),
        "nco_code_3d": Column(str, nullable=True),
        "nco_code_4d": Column(str, nullable=True),
        "nic_section": Column(str, nullable=True),
        "state": Column(str),
        "sector": Column(str, pa.Check.isin(["urban", "rural"])),
        "sex": Column(str),
        "age": Column(int, pa.Check.in_range(0, 120)),
        "education": Column(str, nullable=True),
        "formal": Column(bool, nullable=True),
        "earnings": Column(float, nullable=True),
        "exposure_beta": Column(float, pa.Check.in_range(0, 1), nullable=True),
    },
    strict=True,
)

# EPFO monthly payroll panel: one row per (data_month, measure, age_band,
# gender, industry, state), NULL for undefined dimensions. Tightened to the real
# release structure (see src/ingest/epfo.py): national tables carry all four
# measures; gender tables carry the three gross flows; state/industry tables
# carry net payroll only. Values are net of exits, so negatives are legitimate
# for net_payroll (gross measures are checked >= 0 at ingest).
epfo_payroll = pa.DataFrameSchema(
    {
        "data_month": Column(str, pa.Check.str_matches(r"^\d{4}-\d{2}$")),
        "source_release": Column(str, pa.Check.str_matches(r"^(epfo|mospi)_\d{4}-\d{2}$")),
        "measure": Column(
            str,
            pa.Check.isin(["net_payroll", "new_subscribers", "ceased", "rejoined"]),
        ),
        "age_band": Column(
            str, pa.Check.isin(["<18", "18-21", "22-25", "26-28", "29-35", ">35"])
        ),
        "gender": Column(
            str,
            pa.Check.isin(["male", "female", "transgender", "not_available"]),
            nullable=True,
        ),
        "industry": Column(str, nullable=True),  # EPFO industry heads, as printed
        "state": Column(str, nullable=True),
        "value": Column(int),
        # True for pre-Apr-2020 (MoSPI-vintage) months; the Feb-Mar 2019 and
        # Nov 2019 - Mar 2020 holes are documented in data/raw/epfo/NOTES.md
        "series_break_flag": Column(bool),
    },
    strict=True,
)

# De-identified postings corpus (Golden Rule 9: de-identified at ingest).
postings = pa.DataFrameSchema(
    {
        "posting_id": Column(str, unique=True),
        "source": Column(str, pa.Check.isin(["ncs"])),  # extend only after scraping gate
        "posted_month": Column(str, pa.Check.str_matches(r"^\d{4}-\d{2}$")),
        "title": Column(str),
        "description": Column(str, nullable=True),
        "nco_code_3d": Column(str, nullable=True),  # LLM-assigned, kappa gate applies
        "city": Column(str, nullable=True),
        "city_tier": Column(str, nullable=True),
        "offered_salary": Column(float, nullable=True),
        "required_experience_years": Column(float, nullable=True),
        "fresher_eligible": Column(bool, nullable=True),
    },
    strict=True,
)
