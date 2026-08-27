# Paper Skeleton & Storyline — AI Exposure Atlas (IGIDR Paper 1)

Structure follows ANALYSIS_PLAN §7 (8 sections, 25-30pp + appendix). Prose: Surya.
Status: exhibits marked [BUILT] exist (PRELIMINARY per D6); [PENDING] depend on
gated decisions. Storyline current as of Aug 24, 2026.

## The one-paragraph storyline

India's growth model is services-led — and generative AI lands precisely on the
tasks that model exports. Yet every claim about India's AI exposure routes
through a lossy crosswalk from US O*NET occupations. We build the first
India-native exposure index on NCO-2015 task content, project it onto 460+
million workers in PLFS, and find a double-edged headline: exposure is RARE
(mean score 0.086; four in five workers are barely exposed) but CONCENTRATED
exactly where India's modern economy lives — high-exposure occupations hold
under 2% of workers but 7% of the wage bill, and exposure rises through every
zoom toward the organised urban core: cities (2×), graduates (3×), the
organised sector (where the gender gap flips against women), and — sharpest of
all — the youngest white-collar cohorts, who are twice as likely as their
seniors to sit in high-exposure occupations. India's fresher pyramid stacks
its entrants exactly where AI lands. Turning from measurement to demand: EPFO
payroll shows no statistically detectable young-cohort decline in exposed
industries yet (point estimates uniformly negative, power-limited) — the
canary is sitting in the most exposed part of the mine, but it hasn't sung.
The stakes: whether this becomes augmentation or displacement is not
predetermined — and 40% of white-collar exposure runs through tooling (E2),
making India's outcome contingent on adoption, not just capability.

## Section-by-section

### 1. Introduction (~3pp)
- Hook: Viksit Bharat / services-led growth stakes (Rodrik; Fan-Peters-Zilibotti;
  Nayyar) meets GenAI; the AEI India facts (45% of Indian usage = software occupations).
- The measurement gap: no India-native index; O*NET crosswalk lossiness is
  quantifiable and we quantify it.
- Preview headline numbers + the concentric-circles arc (economy → urban →
  white-collar → organised women → young entrants).
- Claim discipline: measurement-first (D4); demand-side results are supporting.

### 2. Literature & contribution (~2.5pp)
- Strand A (measurement): Eloundou template; Felten robustness; AEI as
  revealed-usage complement; Copestake et al. as closest India paper (pre-GenAI,
  skills not tasks). Gap: India-native task exposure, GenAI period.
- Strand B (effects): Brynjolfsson-Chandar-Chen canaries; Brynjolfsson-Li-Raymond
  augmentation-for-novices; our Section 6 is the India test.
- Steelman up front (Evans 2026): exposure ≠ prediction; our answer = direction-
  neutral measurement + realized-demand tests + sign-symmetric interpretation.

### 3. Index construction & validation (~4pp)
- NCO-2015 Vol II parsing: 3,442 occupations, 18.6k task statements. [BUILT]
- Rubric: Eloundou adapted, E0/E1/E2, 9 decision rules incl. Indian-context
  (language, cash, field presence, attainability baseline). Verbatim in appendix.
- Aggregations α/β/ζ; notation: call the index "E-score" to avoid regression-β collision.
- Validation subsection [PENDING — the paper's load-bearing wall]: fresh 200-task
  blind human subsample under frozen rubric; report κ + confusion matrix.
  Pilot κ history (0.59/0.54) reported honestly as rubric-development iterations;
  managerial-task ruling documented. Human-vs-LLM index variants as bounds
  exhibit (Surya's sensitivity idea).
- Known threats: dated NCO text (→E1+ variant [PENDING postings]), LLM scoring
  its own kind (→validation + rubric verbatim), thin-text occupations (n<5 flagged).

### 4. The Atlas: who is exposed (~6pp) — the paper's core
- Exhibit 4.1 [BUILT]: distribution — exposure is rare (mean 0.086, 80% below 0.1).
- Exhibit 4.2 [BUILT]: headcount vs wage bill — 1.9% of workers, 7.1% of wage
  bill in high-exposure groups; wage-bill mean 1.8× headcount. (India-specific
  headline: exposure of earnings ≫ exposure of people.)
- Exhibit 4.3 [BUILT]: top groups table (software 0.74, finance 0.63, clerks
  0.58...) with employment shares — "high exposure is a thin slice."
- Exhibit 4.4 [BUILT]: cuts — urban 2× rural; education gradient convex (takes
  off only at graduation); formality proxy 4.4×.
- Exhibit 4.5 [BUILT]: states — Delhi/Kerala/Haryana/Telangana top; Bihar bottom.
- Exhibit 4.6 [BUILT]: white-collar deep dive — 14% of employment, 39% of wage
  bill, E-score 3× economy; α vs ζ channel split (40% of exposure is
  tooling-dependent → adoption-contingent impact).
- Exhibit 4.7 [PENDING crosswalk work]: India-native vs O*NET-crosswalked index —
  employment-weighted size of the measurement error the literature accepts.
- Exhibit 4.8 [PENDING]: AEI revealed-usage comparison — exposure vs actual
  Claude usage by occupation; the adoption-gap scatter.
- Self-employment cell (100×-IC touchpoint): own-account professionals vs
  salaried within white-collar. One row, one sentence.

### 5. Gender (~2.5pp) — conference cross-cutting theme, own section
- Exhibit 5.1 [BUILT]: the sign flip — economy-wide women < men (0.073 vs
  0.091, composition: agriculture); organised sector women > men (0.259 vs
  0.248; high-exposure share 20.8% vs 17.3%).
- Decomposition [TO BUILD, data ready]: between-occupation composition vs
  within-occupation; clerical/BPO concentration.
- Framing: the women most attached to modern-sector employment are the most
  exposed — inclusion stakes for the skilling agenda.

### 6. Canaries: the entry rung (~4pp)
- Opener, Exhibit 6.1 [BUILT]: entry-rung gradient — young white-collar workers
  2× seniors' high-exposure share; 3.5M young workers on the most exposed rungs.
  "The fresher pyramid stacks entrants where AI lands."
- EPFO design: 88-month panel, head-level exposure assignment (crosswalk),
  granularity check η²=0.55 [BUILT — Surya to ratify].
- Exhibit 6.2 [BUILT]: event study — imprecise null, uniformly negative point
  estimates, flat pre-trends, 2023H1 dip. Stated as power-limited lower-bound
  evidence; NOT overclaimed either direction.
- Fresher-postings DiD [PENDING corpus decision — now load-bearing for Design 2].
- Limitations with teeth: EPFO = organised margin only (solo/creator migration
  invisible → estimates are reallocation lower bounds); 16 clusters; net flows.

### 7. Policy discussion (~2pp)
- Frame, don't overreach: three implications. (a) Skilling should target the
  E2/tooling channel (40% of white-collar exposure needs adoption infrastructure);
  (b) entry-rung monitoring as an early-warning system (EPFO age bands as the
  ongoing canary dashboard); (c) inclusion: organised-sector women + new
  graduates are the exposed frontier, not farmers.
- Augmentation-vs-displacement: sign-symmetric reading; Brynjolfsson-Li-Raymond
  novice-gains mechanism cuts both ways for a fresher-pyramid economy.

### 8. Conclusion (~1pp)
- The atlas as public good: index CSV + rubric released (repo already public, D7).
- What would change our minds; the monitoring agenda.

### Appendices
- A: rubric verbatim + worked examples; B: validation stats, κ history, confusion
  matrices; C: NCO parsing + coverage; D: crosswalk detail (EPFO→NIC; NCO→SOC);
  E: robustness menu results; F: data provenance manifests.

## Claim-discipline ladder (referee armour)
1. Measured: task exposure on NCO-2015 (validated, post-κ). May claim as fact.
2. Descriptive: atlas cuts, gradients, concentric circles. "Is associated with."
3. Suggestive: EPFO event study. "Point estimates consistent with, not
   statistically distinguishable."
4. Never: displacement predictions, job-loss counts, causal AI→employment claims.

## Blocking dependencies before any of this is writable as final
1. Rubric ruling (managerial tasks) + freeze → paper-grade 3-sample rescore →
   fresh 200-task blind validation κ ≥ 0.7 (Golden Rules 1/4; D6).
2. Postings corpus decision (Lightcast / foundit / Adzuna) → §4 E1+ variant,
   §6 fresher DiD, Exhibit 4.7.
3. Surya ratifies granularity check + crosswalk v0.1.
