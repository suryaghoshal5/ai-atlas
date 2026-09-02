# EPFO series notes

Document every detected series break or definition change here before dummying it out (never splice silently).

## Release anatomy and stitching strategy (2026-08-24, ingest build)

EPFO "Provisional Estimate of Net Payroll" releases are cumulative and revised, with a
two-month data lag, and carry **monthly detail only for the current fiscal year** —
earlier years collapse to FY aggregates. The latest release therefore does NOT contain
the full monthly back-series (verified on epfo_September-2025.pdf: monthly rows exist
only for Apr–Jul 2025). `src/ingest/epfo.py` stitches the panel from the *last* release
that reports each block of months monthly (normally the May release of the following FY).
Exception: EPFO switched to single-month releases for Mar–May 2024, so FY2023-24 needs
epfo_February-2024 (Apr–Dec 2023) + March/April/May-2024 (Jan/Feb/Mar 2024).

**Vintage caveat:** monthly values are the last monthly-reported vintage; later releases
keep revising the FY aggregates as exits accumulate (e.g. Apr-2020 net payroll for <18
was 933 in the Jan-2021 release, 873 in Mar-2021, 861 in May-2021 — the parsed value).
Summing parsed months within a FY will therefore NOT reproduce the FY aggregate printed
in later releases. This is inherent to the source; do not "correct" it.

## Coverage gaps (known-unrecoverable, dummy out in analysis)

- **Feb-2019 and Mar-2019**: after the 25-Mar-2019 MoSPI release (monthly through
  Jan-2019), MoSPI switched to FY-total + current-month format; no archived release
  reports these two months monthly. (This extends the gap named in the acquisition
  notes, which listed only Nov-2019 onward.)
- **Nov-2019 – Mar-2020**: the Dec-2019 MoSPI release ends at Oct-2019; EPFO-native
  monthly tables start Apr-2020. Unrecoverable.

## Series break / measure regime (series_break_flag)

Rows with `data_month < 2020-04` (`series_break_flag = True`) come from MoSPI
"Payroll Reporting in India" releases (mospi_2019-03 for Sep-2017–Jan-2019,
mospi_2019-12 for Apr–Oct 2019): monthly gender × age × {new, ceased, rejoined} only —
**no net_payroll measure** (EPFO's net column starts with the Apr-2020-era format).
The identity net = new − ceased + rejoined holds exactly in all EPFO-era rows, so a
pre-2020 net series is derivable, but it is not an observed printed value and the
1.5-year hole sits between the regimes — treat pre-Apr-2020 as a separate segment.
Gender label difference: MoSPI releases head the third gender column "Others";
EPFO-era releases head it "Transgender". The parser maps both to `transgender`.

## Raw-PDF defects found (deterministic fixes applied by the parser, all logged)

- epfo_May-2021-1.pdf, state pages 14–18 and industry pages 19–20: the Apr-2020 column
  is mis-headed "Apr-19" (the <18 state page heads it "Apr-20"; the value sequence —
  COVID negatives followed by May-20, Jun-20, … — pins it). Fixed via an explicit
  HEADER_FIXES entry.
- epfo_May-2025.pdf, page 33: the "A - <18" row label of the March-2025 gender block
  extracts as a stray glyph. The row's values are clean and row-sum-validated; it is
  assigned as the block's only missing band and logged.
- mospi Dec-2019 release, page 3: the October-2019 sub-header is garbled by interleaved
  rotated text; column positions are unchanged, so a positional template (validated
  against every legible header cell and per-row totals) is used, and logged.
- Industry-head spelling varies across releases: the 2024 releases truncate
  "…USAGE OF COMPUTERS" to "…USAGE OF COMP". Canonicalised to the full head via
  INDUSTRY_FIXES in the parser.
- FY-aggregate table typo in mid-2024–mid-2025 EPFO releases: the 2019-20 × 22-25 cell
  shows 1771707 (a copy of 18-21 × 2018-19); corrected again in epfo_September-2025.
  Irrelevant to the panel (FY rows are never parsed), noted for awareness.

## Exit-recording lag inflates the freshest months' net additions (2026-09-01)

Diagnosed while explaining the apparent mid-2025 "hiring surge" in the age-band trend
chart. Net = new − ceased + rejoined, and **ceased members are recorded only when the
exit claim/transfer is filed — months after the actual exit**. So the last ~2–4 data
months of any release systematically understate exits and overstate net additions;
later releases revise them down (consistent with the downward-revision pattern in the
vintage caveat above).

Evidence from our own panel (national totals):
- Steady-state ceased ≈ 1.7–1.8M/month (2024-06…09, seasoned vintages).
- 2025-06 ceased = 1.005M and 2025-07 ceased = 0.518M (2–3 months mature at the
  epfo_2025-09 release) → net jumps to 1.91M / 2.10M.
- 2025-04, five months mature in the same release, already shows ceased back at 1.45M.
- Gross new subscribers stay flat (0.75–1.1M/month through 2024–25) — no real hiring
  surge underlies the net spike, and the spike appears identically in every age band
  (an artifact signature, not a cohort story).

Handling: (a) trend charts draw rolling means that touch data months ≥ 2025-03 as a
dashed "provisional" tail with a subtitle caveat; (b) event-study month FE absorb the
aggregate artifact, but note in §6 limitations that vintage maturity could differ
across industry heads in recent months; (c) prefer **new subscribers (gross joins)**
for entry-rung visuals — that series does not depend on lagged exits. Do NOT
"correct" the raw values; this is inherent to the source.

## Age bands are flow cross-sections, not cohorts (2026-09-02)

Raised by Surya on the indexed trend chart. EPFO publishes net additions by AGE BAND;
there is no cohort linkage. Implications for interpretation:
- A continuously-employed member ageing across a band boundary generates no flow
  (correct — nothing added or lost).
- But an entry and its eventual reversing exit land in DIFFERENT bands: join at 24
  → +1 in 22-25; exit at 27 → −1 in 26-28. Young-band net is therefore ~pure gross
  entry, while older-band net absorbs exits of workers hired years earlier. Never
  compare band levels as if they were age-specific hiring rates.
- Within-band-over-time (the indexed chart) avoids the level trap but is still not
  cohort-clean: changes in churn timing and in the SIZE of the population cohort
  currently passing through a band move the line without any change in hiring
  propensity per person.
Handling: chart subtitles state "flow snapshots, not tracked cohorts"; the event
study's young-vs-old contrast is within industry × month (netting aggregate churn
shifts); population-cohort normalisation (dividing by projected cohort size) is a
possible robustness step for the paper. Cannot be fixed from published EPFO data.
