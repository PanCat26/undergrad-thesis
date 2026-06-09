from app.agent.ask import _finalize, _make_diff, _register


def test_make_diff_shows_changed_lines() -> None:
    diff = _make_diff("main.tex", "line one\nline two", "line one\nline TWO")
    assert "-line two" in diff
    assert "+line TWO" in diff


def test_register_dedupes_same_source_and_page() -> None:
    registry: list[dict] = []
    first = _register(registry, kind="source", filename="x.pdf", loc={"page": 1}, source_id="s1")
    again = _register(registry, kind="source", filename="x.pdf", loc={"page": 1}, source_id="s1")
    other = _register(registry, kind="source", filename="x.pdf", loc={"page": 2}, source_id="s1")
    assert first == again  # same source + page reuses the index
    assert other != first
    assert len(registry) == 2


def test_finalize_renumbers_dedupes_and_drops_strays() -> None:
    registry = [
        {"index": 1, "kind": "source", "filename": "A.pdf", "loc": {"page": 1}, "source_id": "a"},
        {"index": 2, "kind": "source", "filename": "B.pdf", "loc": {"page": 3}, "source_id": "b"},
        {"index": 3, "kind": "source", "filename": "A.pdf", "loc": {"page": 1}, "source_id": "a"},
    ]
    text = "First [2] then [1] and again [3] plus stray [99]."
    cleaned, citations = _finalize(text, registry)

    # appearance order: [2]->1 (B), [1]->2 (A), [3] is the same source/page as [1] -> 2, [99] dropped
    assert cleaned == "First [1] then [2] and again [2] plus stray."
    assert [c["index"] for c in citations] == [1, 2]
    assert [c["filename"] for c in citations] == ["B.pdf", "A.pdf"]
