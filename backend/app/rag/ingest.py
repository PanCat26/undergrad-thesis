import uuid

from fastapi.concurrency import run_in_threadpool

from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.models.source import Source
from app.rag import qdrant
from app.rag.chunk import chunk_segments
from app.rag.embeddings import embed_texts
from app.rag.extract import extract_segments
from app.storage import get_storage

logger = get_logger("app.ingest")


async def ingest_source(source_id: uuid.UUID) -> None:
    """Background task: extract → chunk → embed → upsert to Qdrant, tracking status."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        source = await session.get(Source, source_id)
        if source is None:
            return
        try:
            data = await run_in_threadpool(get_storage().read, source.storage_key)
            segments = await run_in_threadpool(extract_segments, data, source.ext)
            chunks = await run_in_threadpool(chunk_segments, segments)
            if chunks:
                vectors = await embed_texts([c["text"] for c in chunks])
                await qdrant.upsert_chunks(
                    source.project_id, source.id, source.kind, source.filename, chunks, vectors
                )
            source.status = "ready"
            source.chunk_count = len(chunks)
            await session.commit()
            logger.info("ingested source %s (%d chunks)", source_id, len(chunks))
        except Exception as exc:  # noqa: BLE001 — record any failure on the source row
            logger.exception("ingestion failed for source %s", source_id)
            source.status = "failed"
            source.error = str(exc)[:1000]
            await session.commit()
