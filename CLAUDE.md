# CLAUDE.md — AI Exposure Atlas (IGIDR Paper 1)

## Project Overview

Empirical economics paper for the IGIDR Fourth Biennial Conference on Development (Dec 21-22, 2026, Mumbai). Builds the first India-native generative-AI exposure index for NCO-2015 occupations, projects it onto PLFS microdata (exposure by sector, state, gender, formality, education), and tests labour-demand effects via (a) a postings diff-in-diff (exposure × post-ChatGPT) and (b) an entry-level "canaries" analysis using EPFO payroll data. Solo author: Suryadip Ghoshal. Two research designs, one paper, one shared data pipeline.

Output: LaTeX/Word paper draft + reproducible Python pipeline. Docs to this vault folder; code and data to `/Users/suryadip/Library/CloudStorage/Dropbox/Interest - Non Work/AI Exposure Atlas/` (repo relocated from `~/dev/ai-exposure-atlas/` on Jul 17, 2026, per Surya).

Full analysis plan: see `ANALYSIS_PLAN.md` in this folder. Sprint tasks: see `CURRENT_SPRINT.md`.

## Non-Negotiable Rules (Golden Rules)

1. **This is an academic deliverable. Every number in the paper must be traceable to a script, a dataset version, and a run log. No fabricated data, no silent approximations, no hand-edited results.**
2. Never claim causality the design does not support. The exposure atlas is measurement. The postings DiD supports "labour demand shifted in exposed occupations," nothing stronger. Language in all drafts must match this.
3. All LLM classification calls go through a single module (`src/llm/score.py`) with cached, versioned, seeded prompts. No ad-hoc API calls scattered in notebooks.
4. Every LLM-scored output must have a human-validated subsample (minimum 200 items per classification task) with reported agreement statistics (Cohen's kappa). No LLM score enters the paper without validation.
5. Never scrape in violation of a site's terms of service or robots.txt. Prefer the government NCS open vacancy data and licensed/public datasets. STOP and confirm before any scraping target is added.
6. PLFS, EPFO, and NCO source files are read-only. Never modify raw data; all transformations produce new versioned files in `data/processed/`.
7. Exposure index methodology follows the Eloundou et al. (2024) rubric adapted to NCO-2015, as specified in ANALYSIS_PLAN.md §2. Do not invent alternative scoring rubrics without a STOP.
8. All regressions must be reproducible from `make results`. Regression harness delta reported before every commit.
9. No personal data. Postings are de-identified at ingest (drop recruiter names, emails, phone numbers). Nothing individual-level leaves `data/raw/`.
10. Paper prose is written by Surya. Claude Code produces analysis, tables, figures, and bullet-point findings memos — not manuscript paragraphs. (IGIDR requires AI-generated content be kept to a minimum; similarity index ≤10-15%.)
11. Scope freeze: Designs 1 and 2 only. Do NOT add the Account Aggregator study, GCC analysis, or any new research question.

## Tech Stack

| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.11+ |
| Data | pandas, polars, pyarrow | latest stable |
| Econometrics | statsmodels, linearmodels, pyfixest | latest stable |
| LLM classification | Anthropic API, claude-sonnet-4-6 | pinned in config |
| Validation | pandera schemas + pytest harness | latest stable |
| Figures | matplotlib (paper style, no seaborn defaults) | latest stable |
| Paper | LaTeX (Overleaf-compatible) | — |
| Repo | git, local + GitHub **public** (github.com/suryaghoshal5/ai-atlas; D7) | — |

Do NOT use: Jupyter notebooks as source of record (exploration only, promoted to scripts), R, cloud data warehouses, Dask/Spark (data fits in memory), any non-Anthropic LLM for classification (single-model consistency).

## What Is Already Built

| Feature | Status | Location |
|---|---|---|
| Research designs + literature scan | Done | This chat → `ANALYSIS_PLAN.md` |
| Repo scaffold (uv project, Makefile, pandera schemas, LLM score module w/ cache+majority-vote, regression harness skeleton, pytest suite) | Done (Jul 17, 2026) | `/Users/suryadip/Library/CloudStorage/Dropbox/Interest - Non Work/AI Exposure Atlas/` |
| Data acquisition: NCO-2015 Vol I/II-A/II-B, EPFO payroll archive (2018–Sep 2025 releases), PLFS 2022-23 + 2023-24 unit CSVs + docs, NCS postings audit — all manifested (sha256/source/timestamp) | Done (Jul 17, 2026) | `data/raw/{nco,epfo,plfs,postings}/` |
| NCO Vol II parser (3,442 entries) + 50-occupation pilot selector (400 tasks, 90.7% employment coverage, deterministic) | Done (Jul 17, 2026) | `src/ingest/nco.py`, `src/ingest/pilot_select.py`, `outputs/pilot/pilot_scoring_sheet.csv` |
| Everything else | Not started | — |

(Update this table as components land. If this table says "not started," do not assume prior code exists anywhere.)

## Current Focus

See `CURRENT_SPRINT.md`. One sentence: acquire PLFS 2023-24 unit data and NCO-2015 documentation, and manually score 50 occupations to prove the rubric before building the pipeline.

## Research Context & Literature Survey

Claude Code reads this section to understand what the paper must be positioned against. Anchor papers, what they did, and the gap this project fills.

### Strand A — Measuring AI exposure (Design 1 positions here)

| Paper | Data/Method | Relevance |
|---|---|---|
| Eloundou, Manning, Mishkin & Rock (2024), "GPTs are GPTs", *Science* | Human + GPT-4 rubric scoring of O*NET task exposure to LLMs | **Methodological template.** We adapt this rubric to NCO-2015 task content. |
| Felten, Raj & Seamans (2021), *Strategic Mgmt Journal* | AIOE index linking AI capability benchmarks to O*NET abilities | Alternative index; use for robustness crosswalk comparison. |
| Anthropic Economic Index (Handa et al. 2025; geography report Nov 2025; India brief Feb 2026) | Claude conversation task classification → O*NET | Revealed-usage benchmark. Key India facts: ~45% of Indian usage maps to software occupations (highest globally); per-capita usage 0.27x working-age share; 4 states >50% of usage. Our index is the demand/structure-side complement. |
| Acemoglu, Autor, Hazell & Restrepo (2022), *JOLE* | AI vacancies in Burning Glass postings | Template for postings-based AI demand measurement. |
| Copestake, Marczinek, Pople & Stapleton, "AI and Services-Led Development: Evidence from Indian Job Adverts" | Millions of Indian online vacancies; AI-skill demand pre-GenAI | **Closest India paper.** Their data largely predates ChatGPT; measures AI-skill demand, not task exposure. Our gap: GenAI period + India-native task exposure. |

**Gap claimed by Design 1:** No exposure index exists built on Indian occupational architecture (NCO-2015) and Indian task content; all India claims currently route through lossy US O*NET crosswalks.

### Strand B — AI effects on labour markets, entry-level (Design 2 positions here)

| Paper | Data/Method | Relevance |
|---|---|---|
| Brynjolfsson, Chandar & Chen (2025), "Canaries in the Coal Mine" | US payroll (ADP) microdata; entry-level employment in AI-exposed occupations post-2022 | **Design 2 template.** We replicate the design logic with EPFO age-banded payroll + postings. |
| Brynjolfsson, Li & Raymond (2025), *QJE* | GenAI assist for (offshore BPO) support agents; largest gains for novices | Mechanism evidence; direct India relevance via BPO. |
| Copestake et al. (above) | Postings DiD | Wage/displacement patterns within firms, pre-GenAI baseline. |
| ILO / World Bank India digitalisation & employment reports; NITI Aayog gig reports | Survey/descriptive | Policy framing, not identification. |

**Gap claimed by Design 2:** No India test of entry-level displacement despite India's IT-BPM fresher-pyramid hiring model being the sharpest possible test bed; EPFO monthly age-banded payroll data makes it feasible with public data.

### Strand C — context strands (cite, do not compete)

- DPI economics: Crouzet, Gupta & Mezzanotti (2023, *JPE*); Alok, Ghosh, Kulkarni & Puri (2024-25, NBER) — cite for India digital-adoption context only.
- Structural transformation: Rodrik (premature deindustrialization); Fan, Peters & Zilibotti (2023, *Econometrica*); Nayyar et al. *At Your Service?*; Acemoglu (2024, "Simple Macroeconomics of AI") — frame the services-led-growth stakes in intro/conclusion.

### Literature workflow rules

- Maintain `references.bib` in this folder as the single bibliography source; every claim memo cites bib keys.
- Any NEW anchor paper found during the build goes into `LIT_LOG.md` with 3 lines: claim, method, why it matters to us. STOP if a paper is found that appears to already do Design 1 or Design 2 for India.
- Conference sub-themes to align framing with: "AI, Inequality, and Inclusive Growth" and "AI, Employment, and the Future of Work"; gender is the cross-cutting theme and gets its own results section, not a footnote.

## Architecture & Data Flow

```
data/raw/plfs/          PLFS 2023-24 unit-level (MoSPI download, read-only)
data/raw/nco/           NCO-2015 volumes (occupation task descriptions)
data/raw/postings/      Vacancy corpus (NCS open data + licensed/scraped per gate)
data/raw/epfo/          EPFO monthly payroll releases (age-banded new subscribers)
        │
        ▼
src/ingest/             parsers → data/processed/*.parquet (pandera-validated)
src/llm/score.py        exposure scoring: NCO task statements → rubric scores (cached, versioned)
src/index/build.py      task scores → occupation-level exposure index (E1 core, E1+ with postings tasks)
src/merge/plfs.py       index × PLFS → worker-level exposure dataset
src/analysis/atlas.py   Design 1 descriptives: exposure by sector/state/gender/formality/education
src/analysis/did.py     Design 1 DiD: postings outcomes ~ exposure quintile × post-Nov-2022
src/analysis/canary.py  Design 2: EPFO young-cohort payroll + fresher postings, event study
        │
        ▼
outputs/tables/  outputs/figures/  (versioned, regenerated by `make results`)
paper/           LaTeX manuscript (Surya-authored prose)
```

Pipeline order is strict: no analysis runs on unvalidated processed data; no index build before validation subsample clears kappa ≥ 0.7 (STOP if below).

## Failure Handling

- LLM returns malformed/refused scoring output → retry once with stricter system prompt; on second failure, log task ID to `logs/score_failures.csv` and continue; batch fails if >2% of tasks unresolved.
- LLM score vs human validation kappa < 0.7 → STOP. Do not proceed to index build; surface disagreement examples for rubric revision.
- Postings source unavailable/blocked → do not rotate IPs or evade; log, fall back to NCS open data only, flag corpus-size impact in CURRENT_SPRINT.md.
- PLFS/NCO occupation code fails to match index → report match rate; if <90% of PLFS employment weight covered, STOP with unmatched-code list.
- EPFO series break or definition change detected → document in `data/raw/epfo/NOTES.md`, dummy out the break, never silently splice.
- pandera schema violation on ingest → hard fail with row samples; never coerce silently.
- Regression harness delta shows result sign/significance flip after a code change → STOP, bisect, report before commit.
- Anthropic API rate limit / cost overrun (>USD 200 cumulative scoring spend) → pause batch, report spend, await confirmation.

## Confirmation Gates

**Stop and confirm before:**
- Adding any scraping target or changing postings acquisition strategy
- Any change to the exposure rubric or index formula after first full index build
- Model selection changes (moving off claude-sonnet-4-6)
- Dropping/adding a research question, outcome variable, or identification strategy
- Deleting any file in `data/`
- Any spend beyond the API budget above
- Declaring a result "final" for inclusion in abstract or paper
- Anything touching Think360 systems or data (this is a personal project; keep it that way)

**Proceed autonomously:**
- Ingest parsers, schema validation, tests, logging, caching
- Descriptive tables/figures iterations, formatting
- Robustness variants already listed in ANALYSIS_PLAN.md §5
- Bug fixes, refactors that keep the harness green
- Bib maintenance, LIT_LOG entries

## Environment Variables

| Var | Purpose | Notes |
|---|---|---|
| ANTHROPIC_API_KEY | LLM scoring | never logged, never committed |
| ATLAS_DATA_DIR | root of data/ | defaults to repo-local `data/` |
| ATLAS_RUN_SEED | global seed | default 42; recorded in every output's metadata |

## Key File Map

```
/Users/suryadip/Library/CloudStorage/Dropbox/Interest - Non Work/AI Exposure Atlas/
├── CLAUDE.md                 # symlink/copy of this file
├── CURRENT_SPRINT.md         # ephemeral sprint state (source of truth in vault)
├── Makefile                  # ingest / score / index / results / test targets
├── src/                      # per Architecture section above
├── tests/                    # pytest + regression harness (golden outputs)
├── data/{raw,processed}/     # raw is read-only
├── outputs/{tables,figures}/
├── logs/
└── paper/                    # LaTeX; Surya-authored

Vault (this folder, docs only):
├── CLAUDE.md                 # this spec
├── ANALYSIS_PLAN.md          # detailed analysis plan (authoritative for methods)
├── CURRENT_SPRINT.md         # sprint state
├── LIT_LOG.md                # new literature found during build
└── references.bib            # bibliography source of truth
```

## Design Decisions Log

- D1: Designs 1 (exposure atlas) and 2 (entry-level canaries) combined into one paper; canaries is Section 6, contingent on EPFO data quality. — Rationale: shared pipeline, one submission, deadline Aug 31 abstract.
- D2: Exposure rubric = Eloundou et al. (2024) adapted to NCO-2015, not Felten AIOE. — Rationale: GenAI-specific, task-level, replicable with LLM scoring; AIOE kept as robustness.
- D3: claude-sonnet-4-6 as the single scoring model. — Rationale: consistency, cost, and AEI-comparability of pipeline style.
- D4: Measurement-first framing; DiD is supporting evidence, not headline causal claim. — Rationale: referee honesty; IGIDR referee pool punishes overclaiming.
- D5: Personal project, zero Think360 data or infrastructure. — Rationale: IP cleanliness during exit negotiation.
- D7 (Aug 24, 2026, Surya): repo is PUBLIC at github.com/suryaghoshal5/ai-atlas (overrides the original "GitHub private"). — Rationale: index + rubric are the planned open deliverable anyway. Secret-scan clean (no keys in history/cache); raw data never committed; all committed results carry PRELIMINARY stamps. Accepted trade-off: methodology and preliminary results are visible pre-submission (scoop risk acknowledged).
- D6 (Aug 10, 2026, Surya): **κ gate deferred, not dropped.** Pilot κ failed twice (0.59, 0.54; fault lines: managerial-task definition + E1/E2 seam). Surya's call: proceed with LLM-only ("AI ranking") scoring and index build now so analysis is unblocked; human validation and the managerial-tasks rubric ruling to be revisited BEFORE any result is declared final. **All outputs built on unvalidated scores are stamped PRELIMINARY — none may enter the abstract or paper (Golden Rules 1/4 still bind).** Surya's related idea, to be developed later: publish human-vs-LLM exposure variants with the delta as a sensitivity/bounds exhibit.
- D8 (Sep 2, 2026, Surya): **indexed EPFO age-band chart retired.** EPFO bands are flow cross-sections, not linked cohorts — an entry and its reversing exit land in different bands, and cohort-size shifts move band flows — so the rebased view invites a cohort reading the data cannot support. Levels chart headline reframed to the mechanical entry-age construction. Limitation documented in `data/raw/epfo/NOTES.md`; young-vs-old contrasts live in the event study (within industry × month), with population-cohort normalisation as a candidate robustness step.
