# AI Exposure Atlas — pipeline targets
# Strict order: ingest → score → index → results. No analysis on unvalidated data.

PY := PYTHONPATH=src uv run python

.PHONY: help ingest score index results test harness lint atlas-grid film film-short film-epic validation-sheet validation-kappa

help:
	@echo "Targets:"
	@echo "  ingest   - parse raw PLFS/NCO/postings/EPFO into validated parquet"
	@echo "  score    - LLM exposure scoring of task statements (cached, versioned)"
	@echo "  index    - build occupation-level exposure index from task scores"
	@echo "  results  - regenerate all tables and figures (atlas, DiD, canaries)"
	@echo "  test     - run pytest suite incl. schema tests"
	@echo "  harness  - regression harness: compare outputs against golden copies"
	@echo "  lint     - ruff check"
	@echo "  atlas-grid - 463-square interactive atlas (outputs/atlas_grid/index.html); presentation layer"
	@echo "  film       - ~2.5 min cinematic explainer of the LinkedIn essay (outputs/film/atlas_film.mp4)"
	@echo "  film-short - 90 s cut: 9:16 + 4:5 feed crop + 16:9 (outputs/film/atlas_film_90s_*.mp4)"
	@echo "  film-epic  - 90 s vertical cut in a Rajamouli grammar: gold/fire, drums + choir (9:16 + 4:5)"
	@echo "  validation-sheet - blind 3-rater rating sheets + manual (outputs/validation/)"
	@echo "  validation-kappa - agreement report from the filled rating sheet (kappa gate)"

ingest:
	$(PY) -m ingest.run

score:
	$(PY) -m llm.score

index:
	$(PY) -m index.build

results:
	$(PY) -m analysis.atlas
	$(PY) -m analysis.did
	$(PY) -m analysis.canary

test:
	uv run pytest -q

harness:
	uv run pytest -q tests/test_regression_harness.py

lint:
	uv run ruff check src tests

atlas-grid:
	$(PY) -m insights.atlas_grid

film: atlas-grid
	$(PY) -m insights.film

film-short: atlas-grid
	$(PY) -m insights.film_short --orient vertical --crop45
	$(PY) -m insights.film_short --orient landscape

film-epic: atlas-grid
	$(PY) -m insights.film_epic

atlas-grid-fixture:
	$(PY) -m insights.atlas_grid --fixture

validation-sheet:
	$(PY) -m analysis.validation_sheet

validation-kappa:
	$(PY) -m analysis.validation_kappa
