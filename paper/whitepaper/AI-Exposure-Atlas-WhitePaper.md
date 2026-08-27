---
title: "The AI Exposure Atlas — White Paper Draft"
date: 2026-08-27
doc_type: draft
project: ai-exposure-atlas
status: draft
tags: [project/ai-exposure-atlas, type/whitepaper, status/draft]
---

# The AI Exposure Atlas
### Who in India's workforce is actually exposed to generative AI — measured on India's own terms

> [!warning] PRELIMINARY
> All numbers use machine-only task scoring (human validation in progress, per
> decision D6). Directions and rankings are robust; exact levels may move
> slightly. Nothing here is final until validation clears. Full pipeline:
> [github.com/suryaghoshal5/ai-atlas](https://github.com/suryaghoshal5/ai-atlas)

*Target: 2,800–3,500 words. Section titles are claims. Charts carry the
argument — one every ~300 words. Prose below each heading = content notes to
write from, plus the embedded exhibit.*

---

## 1. 463 million workers, one question  *(~250 words, no chart)*

Open with the tension, not the topic: everyone argues about AI and jobs in
India using numbers imported from America. One concrete image — an actuary in
Mumbai and a crop farmer in Bihar sit at opposite ends of a scale nobody had
built for India, because every existing estimate routes through US O*NET
occupations and a lossy crosswalk.

Thesis, in one line: **exposure is rare, but it is concentrated exactly where
India's modern economy lives — its cities, its graduates, its women in
offices, and above all its youngest white-collar workers.**

TL;DR box (4 bullets):
- Mean exposure across ~463M workers: **0.086** — most of India is out of reach.
- But high-exposure occupations hold **1.9% of workers and 7.1% of earnings**.
- In the organised sector, **women's jobs are MORE exposed than men's** (0.26 vs 0.25).
- Young white-collar workers are in high-exposure jobs at **twice the rate of their seniors** (22% vs 11%).

## 2. The map nobody had  *(~300 words + methodology link)*

Why borrowed numbers fail: US task content, US occupational boundaries,
crosswalk loss. What we did instead, in three sentences: took the government's
own occupation dictionary (NCO-2015: 3,442 occupations, 18,622 task
sentences), scored every task with a fixed public rubric — *could an LLM, or
LLM-powered software, halve this task at equal quality?* (E0 / E1 / E2) — and
projected the scores onto the PLFS labour survey.

![[insight_task_waterfall.png]]
*The pipeline is also the first finding: five in six Indian job tasks are
beyond today's AI — 83% E0, 10% E1 (chat alone), 6% E2 (needs tooling).*

Caveat box goes HERE (not a footnote): preliminary machine scoring; the
human-agreement pilot hasn't yet cleared the pre-registered κ ≥ 0.7 bar;
validation on a fresh blind sample precedes any final claim.
→ Full detail: [[METHODOLOGY]]

## 3. Most of India is out of reach — for now  *(~300 words)*

The anti-hype section, which buys credibility for everything after.

![[insight_exposure_rare.png]]
*80% of workers are in occupations where fewer than one task in ten is exposed.*

![[insight_sector_exposure.png]]
*Agriculture: 194M workers at 0.06. Construction: 60M at 0.03. IT: 7M at 0.54.
Exposure and employment are almost inversely distributed.*

Pivot line to end the section: thin slices can matter enormously — depending
on what they carry.

## 4. Follow the money  *(~300 words)*

The wage-bill asymmetry — the most shareable finding. AI in India is not
primarily a jobs-count story; it is an income-concentration story.

![[insight_wagebill.png]]
*High-exposure occupations: 1.9% of workers, 7.1% of the wage bill — mean
exposure weighted by earnings (0.155) is 1.8× the headcount figure (0.086).*

![[insight_wagebill_sectors.png]]
*In IT, 75% of the sector's paycheque sits in high-exposure occupations;
finance 21%; economy average 7%.*

## 5. Who, exactly  *(~350 words)*

The league table beside the millions view, then the education gradient.
Framing: India's exposure ladder IS its aspiration ladder — the jobs parents
want their children to get are the exposed ones.

![[insight_top_functions.png]]
*Statisticians & actuaries top the league at 0.91 — with only 14k workers.
The frontier is partly an elite of tiny functions.*

![[insight_jobtypes.png]]
*Restrict to groups with real mass and the frontier employs ~13 million:
software developers (3.9M at 0.74), finance professionals (2.1M at 0.63),
numerical clerks, ICT technicians…*

![[insight_education.png]]
*Exposure barely moves from illiterate (0.05) through higher-secondary (0.06),
then triples at graduation (0.16). AI exposure is a graduate phenomenon.*

## 6. The gender flip  *(~250 words)*

Mini detective story. Economy-wide, women look safer (0.073 vs 0.091) — but
that is composition: most female employment is agricultural. Condition on the
organised sector (urban + social-security benefits) and the sign flips.

![[insight_gender_flip.png]]
*Organised-sector women: β 0.259 vs men 0.248; one in five organised-sector
women works in a high-exposure occupation, vs one in six men.*

Inclusion stake in one line: the women who made it into modern-sector
employment are the most exposed to its disruption.

## 7. The entry rung — India's canary  *(~400 words)*

The paper's Design 2, told forward. India's IT-BPM "fresher pyramid" hires at
the bottom; the exposure data shows the bottom rung is where AI lands.

![[insight_entry_rung.png]]
*White-collar workers aged 18–29: mean β 0.32 and 22% in high-exposure
occupations — twice the rate of the 30+ cohort. ~3.5 million young workers sit
on the most exposed rungs.*

Then the test: EPFO monthly payroll (88-month panel), young-cohort net
additions in exposed vs less-exposed industries, before/after ChatGPT.
Honest punchline, verbatim candidate: *point estimates lean negative in every
specification; none is statistically significant. The canary sits in the most
exposed part of the mine — but it hasn't sung.* (Power limits: 16 industry
clusters, net-only flows, crosswalk noise. This honesty is the
differentiator from every doom-thread.)

## 8. The whole atlas on one chart  *(~200 words)*

![[insight_bubble_map.png]]
*Quadrant vocabulary for readers to keep: mass-insulated (crop farmers,
194M); the policy frontier (software, finance, clerks); elite frontline
(actuaries).*

![[insight_bubble_map_whitecollar.png]]
*Zoom into white-collar India: teachers and proprietors are the mass at
moderate exposure; coders, finance and records work are the frontier.*

## 9. What this does NOT say  *(~300 words, no chart)*

The steelman section — address the strongest critiques head-on:
- **Exposure ≠ prediction** (the Benedict Evans critique): task overlap today,
  not a forecast of employment tomorrow; jobs and categories mutate.
- **Augmentation is as live as displacement**: if productivity gains dominate,
  exposed occupations could GROW. Our demand-side tests are sign-symmetric by
  design; the entry-rung result is currently a bounded null, not a verdict.
- **40% of white-collar exposure needs tooling (E2)**: the outcome is
  adoption-contingent — a policy variable, not fate.
- **EPFO sees only the organised margin**: a displaced fresher who turns solo
  creator is invisible there; estimates are lower bounds on reallocation.

## 10. What to watch, what to do  *(~300 words)*

Three concrete implications, no overreach:
1. **Skill for the tooling channel** — the E2 layer (speech, OCR, records
   integration), not chat prompting; that is where 40% of white-collar
   exposure waits on adoption.
2. **Watch the entry rung** — EPFO age bands are a free, monthly early-warning
   dashboard; publish the young-vs-senior hiring gap by industry.
3. **Target inclusion where exposure concentrates** — organised-sector women
   and fresh graduates, not farmers.

Close with the public-good move: the index and rubric are open
(github.com/suryaghoshal5/ai-atlas); here is what would change my mind
(validation shifting scores; the canary singing or clearly not); the full
academic paper is coming (IGIDR, Dec 2026).

---

## Appendix — Methodology
The complete methodology with formulas and worked examples lives in
[[METHODOLOGY]] (same folder). Chart-level numbers: [[provenance]].

## Production notes
- Cut from the academic version: literature review (two name-drop sentences),
  κ history detail (one caveat line), robustness menus, O*NET/AEI comparisons
  (follow-up post when built).
- Series option: §1–5 "the map" / §6–8 "the people" / §9–10 "the meaning" —
  publish flagship first, excerpt later.
- Every chart's source line already carries "preliminary LLM scoring", so
  screenshots stay self-caveating.
