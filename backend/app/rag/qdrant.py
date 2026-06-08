import uuid

from qdrant_client import AsyncQdrantClient, models

from app.config import get_settings

VECTOR_SIZE = 1536


def _client() -> AsyncQdrantClient:
    settings = get_settings()
    return AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


async def _ensure_collection(client: AsyncQdrantClient, name: str) -> None:
    if await client.collection_exists(name):
        return
    await client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
    )
    for field in ("project_id", "source_id", "type"):
        await client.create_payload_index(name, field, models.PayloadSchemaType.KEYWORD)


async def upsert_chunks(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    kind: str,
    filename: str,
    chunks: list[dict],
    vectors: list[list[float]],
) -> None:
    settings = get_settings()
    client = _client()
    try:
        await _ensure_collection(client, settings.qdrant_collection)
        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "type": "source",
                    "project_id": str(project_id),
                    "source_id": str(source_id),
                    "filename": filename,
                    "kind": kind,
                    "text": chunk["text"],
                    "loc": chunk["loc"],
                },
            )
            for chunk, vector in zip(chunks, vectors)
        ]
        if points:
            await client.upsert(collection_name=settings.qdrant_collection, points=points)
    finally:
        await client.close()


async def delete_source(source_id: uuid.UUID) -> None:
    settings = get_settings()
    client = _client()
    try:
        if not await client.collection_exists(settings.qdrant_collection):
            return
        await client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_id", match=models.MatchValue(value=str(source_id))
                        )
                    ]
                )
            ),
        )
    finally:
        await client.close()
