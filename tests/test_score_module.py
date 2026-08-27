"""Offline tests for the LLM scoring module: parsing, caching, majority vote.
No API calls — a fake client is injected."""

from collections import namedtuple

import pytest

from llm import score as score_mod


class FakeClient:
    """Returns queued responses and counts calls."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        text = self._responses.pop(0)
        Block = namedtuple("Block", "type text")
        Msg = namedtuple("Msg", "content")
        return Msg(content=[Block(type="text", text=text)])


def test_parse_score_extracts_last_score_line():
    raw = "Reasoning about the task...\nSCORE: E1"
    assert score_mod._parse_score(raw) == "E1"


def test_parse_score_rejects_garbage():
    assert score_mod._parse_score("I cannot classify this task.") is None
    assert score_mod._parse_score("SCORE: E9") is None


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr(score_mod, "CACHE_DB", tmp_path / "cache.sqlite")
    monkeypatch.setattr(score_mod, "load_rubric_prompt", lambda v: "RUBRIC vtest")
    monkeypatch.setattr(
        "llm.score.logs_dir", lambda: tmp_path / "logs", raising=True
    )
    return tmp_path


def test_majority_vote_and_cache(isolated_env):
    client = FakeClient(["SCORE: E1", "SCORE: E1", "SCORE: E2"])
    result = score_mod.score_task("t01", "Draft routine correspondence", client=client)
    assert result.score == "E1"
    assert not result.tie_escalated
    assert client.calls == 3

    # Second run: all samples served from cache, no new API calls.
    client2 = FakeClient([])
    result2 = score_mod.score_task("t01", "Draft routine correspondence", client=client2)
    assert result2.score == "E1"
    assert client2.calls == 0


def test_tie_escalates_to_human(isolated_env):
    # third sample malformed twice (original + strict retry) -> logged, dropped
    client = FakeClient(["SCORE: E0", "SCORE: E1", "I refuse.\nSCORE: E7", "Still no."])
    result = score_mod.score_task("t02", "Ambiguous task", client=client)
    assert result.score == "TIE"
    assert result.tie_escalated
    assert client.calls == 4
    # The unparseable sample must be logged, not silently dropped.
    failures = (isolated_env / "logs" / "score_failures.csv").read_text()
    assert "t02" in failures
