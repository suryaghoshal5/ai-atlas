"""Shared utilities: paths, config, seed handling, run metadata."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return Path(os.environ.get("ATLAS_DATA_DIR") or REPO_ROOT / "data")


def raw_dir() -> Path:
    # Raw data is read-only (Golden Rule 6). Writers must target processed_dir().
    return data_dir() / "raw"


def processed_dir() -> Path:
    return data_dir() / "processed"


def outputs_dir() -> Path:
    return REPO_ROOT / "outputs"


def logs_dir() -> Path:
    return REPO_ROOT / "logs"


def run_seed() -> int:
    return int(os.environ.get("ATLAS_RUN_SEED", "42"))


def load_config() -> dict:
    with open(REPO_ROOT / "config" / "config.yaml") as f:
        return yaml.safe_load(f)
