"""Ingest orchestrator: parse raw sources into pandera-validated parquet.

Raw files (data/raw/) are read-only; every parser writes new versioned files
to data/processed/ and hard-fails on schema violations with row samples.
"""

from atlas_common import raw_dir

PARSERS = {
    "plfs": "ingest.plfs",       # PLFS 2023-24 / 2022-23 unit-level (MoSPI)
    "nco": "ingest.nco",         # NCO-2015 Vol I & II task statements
    "postings": "ingest.postings",  # NCS open vacancy data (scraping gated)
    "epfo": "ingest.epfo",       # EPFO monthly payroll releases
}


def main() -> None:
    missing = [name for name in PARSERS if not any((raw_dir() / name).iterdir())]
    if missing:
        raise SystemExit(
            f"No raw data present for: {', '.join(missing)}. "
            "Acquire per CURRENT_SPRINT.md before running ingest."
        )
    raise SystemExit("Parsers not yet implemented (Sprint 0: acquisition first).")


if __name__ == "__main__":
    main()
