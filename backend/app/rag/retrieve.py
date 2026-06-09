import uuid
from dataclasses import dataclass

from app.config import get_settings
from app.rag import qdrant
from app.rag.embeddings import embed_texts

# Pull a wider candidate pool than top_k so we can diversify across sources.
_POOL_SIZE = 32


@dataclass
class RetrievedChunk:
    kind: str  # "source" | "draft"
    text: str
    score: float
    loc: dict
    filename: str  # source filename or draft file path
    source_id: str | None = None
    file_id: str | None = None


def _to_chunk(score: float, payload: dict) -> RetrievedChunk:
    return RetrievedChunk(
        kind=payload.get("type", "source"),
        text=payload.get("text", ""),
        score=score,
        loc=payload.get("loc", {}),
        filename=payload.get("filename") or payload.get("path") or "source",
        source_id=payload.get("source_id"),
        file_id=payload.get("file_id"),
    )


async def retrieve(
    project_id: uuid.UUID,
    query: str,
    *,
    types: list[str] | None = None,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Embed the query, search Qdrant, drop low-confidence hits, and diversify across sources.

    Plain top-k clusters on the closest one or two documents; broad questions ("what does
    each paper contribute?") then miss most sources. So we take the best chunk from each
    distinct source first, then fill remaining slots by score.
    """
    settings = get_settings()
    types = types or ["source", "draft"]
    top_k = top_k or settings.rag_top_k

    vectors = await embed_texts([query])
    pool = await qdrant.search(project_id, vectors[0], types, max(_POOL_SIZE, top_k))
    hits = [(score, payload) for score, payload in pool if score >= settings.rag_min_score]

    chosen: list[int] = []
    chosen_set: set[int] = set()
    seen_sources: set[str] = set()

    for index, (_, payload) in enumerate(hits):
        key = payload.get("source_id") or payload.get("file_id") or str(index)
        if key not in seen_sources:
            seen_sources.add(key)
            chosen.append(index)
            chosen_set.add(index)
        if len(chosen) >= top_k:
            break

    for index in range(len(hits)):
        if len(chosen) >= top_k:
            break
        if index not in chosen_set:
            chosen.append(index)
            chosen_set.add(index)

    chosen.sort()  # restore score order (the pool is sorted by descending score)
    return [_to_chunk(*hits[index]) for index in chosen]
