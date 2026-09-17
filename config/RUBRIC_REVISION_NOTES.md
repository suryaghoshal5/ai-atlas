# Rubric revision notes

Running log of ambiguities found in the GenAI exposure rubric
(`config/rubric_v*.md`), with evidence and proposed rulings. Nothing here
changes a score. A rubric change after the first full index build is a
STOP-gated event (CLAUDE.md, Golden Rule 7 and Confirmation Gates); proposals
below wait for Surya's ruling and are then applied together as the next rubric
version, before the human-validation round that decides the κ gate (D6).

Format per entry: id, date, trigger, evidence, proposal, status.

---

## R-01 · Managerial and supervisory statements (v0.1 → v0.2, applied)

- **Trigger.** Pilot round 1 (Jul 2026), κ = 0.59 vs human scores. Largest
  disagreement class: statements whose essence is directing, supervising or
  coordinating people, which the LLM scored E1 (the plan or report can be
  drafted) and the human scored E0 (the authority is the task).
- **Ruling.** Rule 8 added in v0.2: supervision and coordination are E0 by
  default; score E1/E2 only when the statement as written is primarily about
  producing the plan, schedule, roster, report or correspondence.
- **Status.** Applied in v0.2-draft. Round 2 κ = 0.54; the residual
  disagreement moved to R-02. The managerial-task definition is still listed
  in D6 as needing a final ruling.

## R-02 · The E1 / E2 seam (v0.2, open)

- **Trigger.** Pilot rounds 1 and 2. When a text task could be done in a chat
  window but would in practice be done with records, documents or dictation,
  raters split between E1 and E2.
- **Ruling so far.** Rule 9 added in v0.2: if every input and output named in
  the statement is text the worker could paste into a chat window, score E1;
  score E2 only when the statement requires non-text input, an organisation's
  records or systems, or execution.
- **Status.** Open. Round 2 still failed the gate (κ = 0.54; 55 of 383 pairs
  disagree). Candidate refinement: make "named in the statement" strict, so
  that an unnamed source of the inputs never promotes E1 to E2.

## R-03 · Minimal statements naming an input act (Sep 17, 2026, proposed)

- **Trigger.** Surya, reviewing the atlas grid: NCO 4110.0100 (Clerk, General)
  task t02, "May do his own typing.", carries E0 in the full batch; he read it
  as E1.
- **Evidence from the score cache** (`cache/llm_scores.sqlite`, same model,
  temperature 0):
  - rubric v0.2-draft, 3 pilot samples: E0, E2, E0 (majority E0).
  - rubric v0.1-draft, 3 pilot samples: E0, E0, E1.
  - full batch (v0.2, 1 sample): E0.
  The model's three readings are each defensible under the current text. E0:
  the statement names only the physical act of keyboarding and a chat LLM does
  not remove keystrokes. E1: typing exists to produce text, and an LLM
  pre-drafts that text. E2: speech-to-text halves the keying itself. The
  rubric gives no rule for a statement that names an *input act* (typing,
  keying, entering, transcribing) with the content unspecified. Same seam as
  R-02, in its most compressed form.
- **Sensitivity.** One task of 23 moves this occupation's β by ±0.02; group
  411 β by ±0.005. Immaterial to the index, material to κ, because the corpus
  has 1,743 statements under 40 characters (E0 1,550 / E1 91 / E2 89 in the
  full batch) and many of them name an act with no content.
- **Proposed Rule 10 (for v0.3, not applied).** *Input acts with unspecified
  content.* If the statement names only the act of entering, keying, typing,
  transcribing or copying text and does not say what is composed, score by the
  cheapest attainable substitute for the act itself: speech-to-text, OCR or
  copy-paste tooling, hence **E2** when the act produces a document or record,
  **E0** when the act is incidental to a physical task ("keys in the weight
  shown on the scale"). Do not infer an unstated drafting component; that is
  Rule 1 (score the task as written).
- **Status.** Proposed. Needs Surya's ruling. Until then rate under v0.2 and
  write `R-03` in the notes column of the rating sheet whenever this pattern
  is met, so the disagreement is countable.

## R-04 · NCO designation boilerplate (Sep 17, 2026, proposed)

- **Trigger.** Building the rating sheet. 546 task statements are NCO Vol II
  boilerplate that describes a *title*, not an activity: "Is designated
  according to work performed …", "May be designated as …", "May specialise
  in …".
- **Evidence.** Full batch labels for these 546: E0 482, E1 54, E2 9. A
  designation line has no activity to expose; the 63 non-E0 labels are noise
  that leaks into β for the occupations concerned.
- **Proposal.** Two options for Surya. (a) Rubric: add to Rule 1 that a
  statement naming a designation, specialisation or title with no activity is
  E0. (b) Pipeline: drop these lines at ingest (`src/ingest/nco.py`) so they
  never enter the task base; occupation n_tasks falls accordingly. (b) is
  cleaner for the index; (a) keeps the task count comparable to NCO. Rating
  sheet convention meanwhile: raters mark such rows `NA` (see manual §4) and
  they are excluded from κ.
- **Status.** Proposed.

## R-05 · Non-task fragments in the corpus (Sep 17, 2026, pipeline)

- **Trigger.** Same build. Some "statements" are parser fragments: title
  strings in capitals ("LAND RECORD OFFICER.", "SUPPLY OFFICER ."), machine
  names ("-Flat Knitting Machine Operator."). 13 of the 28 tasks the batch left
  unresolved are under 40 characters and most are of this kind.
- **Proposal.** Ingest fix, not rubric: tighten `split_tasks` in
  `src/ingest/nco.py` to drop sentences with no verb or in all capitals, and
  re-run the batch on the residue. Raters mark these `NA` in the sheet.
- **Status.** Proposed; belongs with R-04 (b).
