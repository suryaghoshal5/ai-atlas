# AI Exposure Atlas — pipeline targets
# Strict order: ingest → score → index → results. No analysis on unvalidated data.

PY := PYTHONPATH=src uv run python

.PHONY: help ingest score index results test harness lint atlas-grid

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

atlas-grid-fixture:
	$(PY) -m insights.atlas_grid --fixture
