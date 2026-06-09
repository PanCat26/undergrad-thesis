import uuid

import pytest

from app.rag.retrieve import retrieve


@pytest.fixture
def mock_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.0] * 1536 for _ in texts]

    async def fake_search(project_id, vector, types, top_k):  # noqa: ANN001
        return [
            (0.9, {"type": "source", "text": "relevant", "filename": "a.pdf",
                   "loc": {"page": 2}, "source_id": "s1"}),
            (0.05, {"type": "source", "text": "noise", "filename": "b.pdf",
                    "loc": {}, "source_id": "s2"}),
        ]

    monkeypatch.setattr("app.rag.retrieve.embed_texts", fake_embed)
    monkeypatch.setattr("app.rag.qdrant.search", fake_search)


async def test_retrieve_drops_low_confidence_hits(mock_retrieval: None) -> None:
    chunks = await retrieve(uuid.uuid4(), "what is the method?")
    assert len(chunks) == 1
    assert chunks[0].source_id == "s1"
    assert chunks[0].loc == {"page": 2}
    assert chunks[0].kind == "source"
