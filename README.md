# AI Exposure Atlas

An India-native generative-AI exposure index built on NCO-2015 task content,
projected onto PLFS 2023-24 microdata, with an EPFO entry-level ("canaries")
monitoring specification. Paper prepared for the IGIDR Fourth Biennial
Conference on Development (Dec 2026). Solo author: Suryadip Ghoshal.

**Status: all results are PRELIMINARY.** Task labels are machine-scored
against a fixed public rubric; the human-validation gate (Cohen's κ ≥ 0.7)
has not yet been cleared, and nothing here is final until it is. Bounding
exercises for the validation gap are part of the pipeline (see below).

## Reproducing the paper's numbers

Every number in the paper traces to a script, a dataset version, and a run
log. The front door:

```sh
uv sync                 # Python 3.12 venv with all deps
make ingest             # raw -> pandera-validated parquet (raw/ is read-only)
make index              # task scores -> occupation/group exposure index
make results            # all tables and figures
make harness            # regression check against golden outputs
```

You do **not** need an API key to rebuild the index: every LLM scoring
response is cached in `cache/llm_scores.sqlite`, keyed on (model, rubric
version, prompt, task text, sample index), so `make index` and everything
downstream replays from cache. `make score` (which would hit the Anthropic
API) is only needed to extend scoring; it requires `ANTHROPIC_API_KEY` in
`.env` (see `.env.example`).

Raw source files under `data/raw/` are never committed; each subfolder
carries a `manifest.csv` with SHA-256, source URL, and retrieval timestamp
so the inputs can be re-downloaded and verified byte-for-byte.

## What reproduces what

| Component | Where | Feeds |
|---|---|---|
| NCO-2015 parsing (3,442 entries → 18,622 task statements) | `src/ingest/` | everything |
| Exposure scoring (single gated LLM module, cached, versioned) | `src/llm/score.py`, rubric in `config/rubric_v*.md` | index |
| Index build (α / β / ζ; 122 NCO 3-digit groups) | `src/index/build.py` | atlas |
| PLFS merge (official weights; 99.4% employment coverage) | `src/merge/plfs.py` | atlas cuts |
| Atlas descriptives, entry rung, EPFO event study, typology, GVA bridge | `src/analysis/` | paper tables & figures |
| **Stress tests**: O*NET crosswalk comparison, vintage decomposition, E2-weight sensitivity, human-label substitution bounds | `src/analysis/{crosswalk_compare,vintage_check,e2_sensitivity,validation_bounds}.py` | robustness appendix |
| Media charts for the essay/white-paper versions | `src/insights/` | **not required for any paper number** |

`src/insights/` is presentation-layer only (house-style charts and slides for
the Substack/white-paper editions of the same results); skip it when auditing
the paper.

## Data sources (all public)

- NCO-2015 Vol I/II, Directorate General of Employment
- PLFS 2023-24 unit records, MoSPI (download via microdata.gov.in; not redistributed here)
- EPFO monthly payroll releases (parsing caveats documented in `data/raw/epfo/NOTES.md`)
- NAS Statement 4A (GVA by activity), MoSPI
- Eloundou et al. (2024) O*NET exposure scores + BLS/IBS SOC-ISCO crosswalks (`data/raw/crosswalk/manifest.csv`)

## Guard rails

- `data/raw/` is read-only; all transforms write versioned files to `data/processed/`.
- All LLM calls go through one module with caching and a spend cap; no ad-hoc API calls.
- Regression harness (`make harness`) must stay green; sign/significance flips block commits.
- Scoring model pinned: `claude-sonnet-4-6`, temperature 0.

Spec and decision log: `CLAUDE.md`. A tagged replication release will
accompany the submitted paper.
