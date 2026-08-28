---
title: "AI Exposure Atlas — Methodology"
date: 2026-08-27
doc_type: reference
project: ai-exposure-atlas
status: draft
tags: [project/ai-exposure-atlas, type/methodology]
---

# How the AI Exposure Atlas is built

*Methodology section for the white paper / Substack version. All numbers
PRELIMINARY (machine-only scoring; human validation in progress). Every step
regenerates from the public repo: github.com/suryaghoshal5/ai-atlas.*

## The pipeline in one view

```
NCO-2015 Vol II (3,442 occupation descriptions, DGE)
        │  parse into individual duty sentences
        ▼
18,622 task statements
        │  score each against a fixed rubric (LLM, temperature 0)
        ▼
task labels: E0 (not exposed) / E1 (chat alone) / E2 (needs tooling)
        │  aggregate to occupation groups (share-based formulas)
        ▼
exposure scores per NCO 3-digit group (122 groups)
        │  merge onto PLFS 2023-24 worker records (survey weights)
        ▼
the Atlas: exposure by sector, state, education, gender, age, earnings
        │  map industry heads + monthly payroll (EPFO)
        ▼
the entry-rung ("canaries") analysis
```

## Step 1 — Task statements from India's own occupation dictionary

The National Classification of Occupations (NCO-2015), published by the
Directorate General of Employment, describes every recognised occupation in
India — 3,442 detailed entries — as a paragraph of duties ("Examines vehicle to
ascertain nature and location of defects… Dismantles defective unit…").

We parse each description into individual duty sentences: **18,622 task
statements**. This is the same architecture the influential US studies use
(O*NET task lists), except the task content is *Indian* — written for Indian
workplaces by India's own statistical system. That is the paper's core
methodological claim: no crosswalk through American occupational definitions.

## Step 2 — Scoring each task (E0 / E1 / E2)

Every task statement is scored against a fixed written rubric, adapted from
Eloundou, Manning, Mishkin & Rock (2024, *Science*) with India-specific
decision rules (multilingual work is not protection; cash handling and field
presence are not exposed; attainability assumes smartphone-and-UPI-era access).
The scoring question:

> Would access to an LLM, or LLM-powered software, cut the time to do this
> task by **at least half**, at equal quality?

- **E0** — no: the task's essence is physical or presence-bound.
- **E1** — yes, via a chat interface alone (drafting, analysis, translation…).
- **E2** — yes, but only with LLM-powered software on top (speech-to-text,
  OCR, records integration, code execution).

Scoring is done by claude-sonnet-4-6 at temperature 0 with the rubric as a
fixed prompt (one sample per task in this preliminary pass; the paper-grade
run uses three samples with majority vote). Of 18,622 statements, 18,594
(99.85%) returned a valid label; 28 are logged as unresolved and excluded.
Result: **83% E0, 10% E1, 6% E2** — five in six Indian job tasks are beyond
today's AI even before any employment weighting.

**Status caveat:** these are machine labels. Our human-agreement pilot has not
yet met the pre-registered reliability bar (Cohen's κ ≥ 0.7; two rounds landed
at 0.59 and 0.54, with disagreement concentrated on managerial-coordination
tasks and the E1/E2 boundary). Full human validation on a fresh 200-task
blind sample happens before anything here is called final. Directions and
rankings are robust to this; third-decimal levels are not.

## Step 3 — From task labels to an occupation's exposure score

For an occupation group with *n* scored tasks, let share(E1) and share(E2) be
the fraction of its tasks in each exposed class. Three standard aggregations:

- **α (alpha)** = share(E1) — the chat-only exposure.
- **β (beta)** = share(E1) + ½·share(E2) — the headline score: tooling-dependent
  tasks count half.
- **ζ (zeta)** = share(E1) + share(E2) — the upper bound if tooling arrives.

**Worked example — software developers (NCO group 251), 139 tasks:**
64.0% scored E1, 19.4% scored E2, the rest E0. So
α = 0.640; β = 0.640 + ½ × 0.194 = **0.737**; ζ = 0.835.
Read: "about three-quarters of this group's task content is AI-doable, once
tooling-dependent tasks are discounted by half."

Scores are computed at the occupation level, then aggregated (task-weighted)
to the 122 three-digit NCO groups — the level at which India's labour survey
records occupations.

## Step 4 — Projecting onto the workforce (PLFS)

The Periodic Labour Force Survey 2023-24 gives us 164,523 employed respondents
(principal usual status), each with a 3-digit NCO occupation code, plus state,
sector, sex, age, education, industry, and earnings. Each worker inherits
their occupation group's exposure score. Coverage: **99.4% of employment
weight** matches a scored group.

Every national statistic is **survey-weighted**. PLFS publishes a multiplier
per record; per the official readme, a worker's weight is

```
weight = (MULT/100 if NSS == NSC else MULT/200) / NO_QTR
```

which sums to an estimated **~463 million** principal-status workers. The
employment-weighted mean exposure is then

```
mean β = Σ(weightᵢ × βᵢ) / Σ(weightᵢ)  =  0.086
```

**Wage-bill weighting** replaces the person weight with weight × monthly
earnings (regular-salaried and self-employed earnings; casual daily wages not
yet folded in). That yields wage-bill mean β = 0.155 — 1.8× the headcount
figure — and puts 7.1% of measured earnings, but only 1.9% of workers, in
high-exposure (β ≥ 0.5) occupations.

**Definitions used in the cuts:**
- *White collar* = NCO divisions 1–4 (managers; professionals; technicians &
  associate professionals; clerical).
- *Organised-sector proxy* = urban worker reporting eligibility for any social
  security benefit (PLFS codes 1–7; code 8 = not eligible). It is a proxy,
  defined for wage workers, not the full formality definition.
- *High exposure* = occupation group with β ≥ 0.5.
- Education buckets follow PLFS general-education codes (manual C-19: 08 =
  secondary, 10 = higher secondary, 11 = diploma, 12 = graduate, 13 =
  postgraduate; an earlier draft mis-bucketed these — corrected Aug 28); states use census
  codes; age bands are 5-year.

## Step 5 — The entry-rung analysis (EPFO)

EPFO's monthly payroll releases give net new provident-fund subscribers by age
band, and (from April 2020) by industry head. We parsed the releases into an
88-month panel (Sep 2017 – Jul 2025), verified internally: new − ceased +
rejoined = net holds exactly in every EPFO-era cell.

Because EPFO industries are EPF-Act heads (not standard NIC codes), each head
is hand-mapped to NIC divisions, and its exposure is the employment-weighted
mean β of PLFS workers in those divisions. Head scores span 0.032
(construction) to 0.554 (the computers head), and **55% of worker-level
exposure variance lies between heads** (η², the ANOVA between-group share) —
enough separation to use heads as treatment units.

The event study then asks whether young hiring fell in exposed industries
after ChatGPT (Nov 2022):

```
asinh(net additionsᵢₜ) = γ·(Eᵢ × Postₜ) + industry FE + month FE + εᵢₜ
```

on the 18–25 cohort, with a triple-difference version using 29+ cohorts as the
within-industry comparison (26–28 excluded as a buffer), standard errors
clustered on the 16 industry heads. The asinh transform is used because net
flows can be negative. Result so far: point estimates uniformly negative but
statistically indistinguishable from zero — reported as power-limited, not as
evidence of no effect. Known power constraints: 16 clusters, net-only flows,
and measurement error from the industry crosswalk (which biases toward zero).

## Step 6 — The occupation typology (cluster analysis)

To check that our hand-drawn categories (white collar, high-exposure, sectors)
aren't doing the storytelling for us, we also let the data draw its own map.

**Features.** Each of the 122 occupation groups is described by seven numbers,
all computed employment-weighted from the merged PLFS data: α (chat-only
exposure), E2 share (ζ − α, the tooling-dependent slice), graduate share,
female share, urban share, young share (18–29), and log median monthly
earnings.

**Method.** Features are standardised (z-scores, so no single scale
dominates), then clustered with k-means (50 restarts, fixed seed 42). The
number of clusters is not chosen by us: we fit k = 3 through 7 and keep the k
with the best silhouette score — a standard measure of how cleanly points sit
inside their own cluster versus the nearest other one. k = 5 wins
(silhouette 0.274; k = 4 scores 0.265, k = 6 drops to 0.240). Each occupation
group is one unweighted point in the fit; employment weights enter the
*interpretation* (cluster sizes in workers), not the distance calculation —
so crop farmers' 107M workers don't drag every centroid toward agriculture.

**Output.** Five clusters with employment-weighted profiles (table in the
white paper §8b): frontier professionals; a tooling-exposed paperwork layer;
managers & teachers; the rural agrarian mass; urban manual & retail. The
validation-relevant point: the algorithm reproduced the E1-vs-E2 channel
distinction without being told those were separate features of interest, and
split the insulated mass on geography/gender rather than exposure.

**Caveats.** k-means assumes roughly spherical clusters in feature space and
a silhouette of 0.27 is moderate, not crisp — boundaries between the
managerial middle and the paperwork layer are soft, and a handful of groups
sit near them. The typology is a descriptive lens, not a measurement claim;
cluster labels are ours, membership is the algorithm's. Reproduce with
`python -m analysis.typology` (assignments in
`occupation_typology_PRELIMINARY.parquet`).

## Step 7 — The GVA bridge (what share of the economy's value-add)

Two macro quantifications, both composition arithmetic, neither a forecast:

1. **GVA by exposure band.** NAS Statement 4A (FY2023-24 First Revised
   Estimates, current prices; archived + manifested in `data/raw/nas/`) gives
   GVA for eight economic activities. Each activity's exposure = the
   employment-weighted mean exposure of PLFS workers in its NIC divisions
   (seam handled explicitly: computer services NIC 62-63 sit in NAS
   "Financial, Real Estate & Professional Services"; telecom/broadcasting
   58-61 in the trade-transport-communication group). Results: GVA-weighted
   mean exposure 0.146 vs employment-weighted 0.086; activities above the
   employment-weighted average produce 57.2% of GVA.
2. **Exposed labour income.** Exposure is a labour-task property, so the
   disciplined macro number applies the labour share: high-exposure
   occupations hold 7.1% of measured labour compensation; at India's labour
   income share of GVA (~0.45-0.5, India KLEMS), that is ~3% of GVA flowing
   through high-exposure labour.

**What we refuse to compute:** "GDP at risk/gain" totals — they require an
assumed displacement or productivity-uplift rate, which is a forecast, not a
measurement. We report where value-add is produced; the demand-side sections
test what happens to it.

## What can go wrong (and what we do about it)

1. **The scorer is an LLM judging LLM capability.** Mitigations: fixed public
   rubric, temperature 0, human validation gate before finality, and
   publication of human-vs-machine disagreement as a bounds exhibit.
2. **NCO text is pre-GenAI vintage.** A postings-augmented index variant (E1+)
   is planned once a job-postings corpus is licensed.
3. **Exposure ≠ displacement.** The score measures technical overlap, not
   outcomes; direction is tested separately against payroll and postings data,
   with the augmentation hypothesis given equal footing.
4. **Thin descriptions.** Occupations with <5 task statements are flagged;
   group-level scores are the reliable unit.
5. **Everything is versioned.** Raw files are read-only with SHA-256 manifests;
   every number regenerates from scripts; scoring responses are cached so the
   full index rebuilds without re-querying the model.

*Data: NCO-2015 Vol II (DGE); PLFS 2023-24 unit data (MoSPI); EPFO payroll
releases; all public. Scoring spend to date: ~$41. Code, rubric, manifests:
github.com/suryaghoshal5/ai-atlas.*
