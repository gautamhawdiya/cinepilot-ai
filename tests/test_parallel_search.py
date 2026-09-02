"""Unit coverage for the Parallel integration tool.

No real network calls: the Parallel SDK client is monkeypatched so these
tests verify CinePilot's own result-shaping and failure handling, not
Parallel's live API.
"""

import pytest

from tools import parallel_search as parallel_search_module


class _FakeResultItem:
    def __init__(self, title, url, excerpts):
        self.title = title
        self.url = url
        self.excerpts = excerpts


class _FakeResponse:
    def __init__(self, results):
        self.results = results


class _FakeParallelClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def search(self, objective, search_queries):
        return _FakeResponse(
            [
                _FakeResultItem(
                    "Example Source",
                    "https://example.com/permits",
                    ["Permits are required.", "Book two weeks ahead."],
                ),
                _FakeResultItem(
                    "Another Source",
                    "https://example.com/safety",
                    "Single string excerpt.",
                ),
            ]
        )


def test_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("PARALLEL_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        parallel_search_module.parallel_search(
            objective="test objective",
            search_queries=["test query"],
        )


def test_shapes_results_from_the_live_client(monkeypatch):
    monkeypatch.setenv("PARALLEL_API_KEY", "test-key")
    monkeypatch.setattr(parallel_search_module, "Parallel", _FakeParallelClient)

    result = parallel_search_module.parallel_search(
        objective="Find filming permit requirements",
        search_queries=["warehouse filming permit"],
    )

    assert result["result_count"] == 2
    assert result["results"][0]["title"] == "Example Source"
    assert result["results"][0]["url"] == "https://example.com/permits"
    assert result["results"][0]["excerpts"] == [
        "Permits are required.",
        "Book two weeks ahead.",
    ]
    # A single-string excerpt from the SDK must be normalized to a list.
    assert result["results"][1]["excerpts"] == ["Single string excerpt."]


def test_respects_max_results(monkeypatch):
    monkeypatch.setenv("PARALLEL_API_KEY", "test-key")
    monkeypatch.setattr(parallel_search_module, "Parallel", _FakeParallelClient)

    result = parallel_search_module.parallel_search(
        objective="Find filming permit requirements",
        search_queries=["warehouse filming permit"],
        max_results=1,
    )

    assert result["result_count"] == 1
    assert len(result["results"]) == 1
