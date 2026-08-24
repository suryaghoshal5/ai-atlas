# AI Exposure Atlas

India-native generative-AI exposure index for NCO-2015 occupations, projected onto
PLFS microdata, with postings DiD and EPFO entry-level ("canaries") analyses.
Paper for the IGIDR Fourth Biennial Conference on Development (Dec 2026).
Solo author: Suryadip Ghoshal.

- Spec and golden rules: `CLAUDE.md`
- Methods (authoritative): `ANALYSIS_PLAN.md` in the Obsidian vault
  (`SuryaOS/01-Projects/AI-Exposure-Atlas/`)
- Sprint state: `CURRENT_SPRINT.md`

## Setup

```sh
uv sync                 # creates .venv with Python 3.12 and all deps
cp .env.example .env    # add ANTHROPIC_API_KEY
make test               # schema + scoring-module tests, regression harness
```

## Pipeline

Strict order — each stage gates the next:

```
make ingest    # raw -> pandera-validated parquet (raw/ is read-only)
make score     # LLM exposure scoring (gated on frozen rubric)
make index     # exposure index (gated on validation kappa >= 0.7)
make results   # all tables and figures, reproducibly
make harness   # regression check against golden outputs
```

Raw data under `data/raw/` is never committed and never modified.
All numbers in the paper must be traceable to a script, a dataset version,
and a run log.
