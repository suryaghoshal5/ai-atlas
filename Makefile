# AI Exposure Atlas — pipeline targets
# Strict order: ingest → score → index → results. No analysis on unvalidated data.

PY := PYTHONPATH=src uv run python

.PHONY: help ingest tasks score index typology masters results test harness lint

help:
	@echo "Targets:"
	@echo "  ingest   - parse raw PLFS/NCO/postings/EPFO into validated parquet"
	@echo "  tasks    - split NCO Vol II descriptions into the scored task corpus"
	@echo "  score    - LLM exposure scoring of task statements (cached, versioned)"
	@echo "  index    - build occupation-level exposure index from task scores"
	@echo "  typology - cluster the occupation groups; regenerates the section 8b table"
	@echo "  masters  - three master tables: task / occupation / sector grain"
	@echo "  results  - regenerate all tables and figures (atlas, DiD, canaries, typology, masters)"
	@echo "  test     - run pytest suite incl. schema tests"
	@echo "  harness  - regression harness: compare outputs against golden copies"
	@echo "  lint     - ruff check"

ingest:
	$(PY) -m ingest.run

tasks:
	$(PY) -m ingest.task_statements

score:
	$(PY) -m llm.score

index:
	$(PY) -m index.build

typology:
	$(PY) -m analysis.typology

masters:
	$(PY) -m export.masters

results:
	$(PY) -m analysis.atlas
	$(PY) -m analysis.did
	$(PY) -m analysis.canary
	$(PY) -m analysis.typology
	$(PY) -m export.masters

test:
	uv run pytest -q

harness:
	uv run pytest -q tests/test_regression_harness.py

lint:
	uv run ruff check src tests
