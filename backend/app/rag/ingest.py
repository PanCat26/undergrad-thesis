import uuid

from fastapi.concurrency import run_in_threadpool

from app.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.models.file import ProjectFile
from app.models.source import Source
from app.rag import qdrant
from app.rag.chunk import chunk_segments
from app.rag.embeddings import embed_texts
from app.rag.extract import extract_segments
from app.rag.metadata import fetch_citation
from app.storage import get_storage

# Cap how much text we scan for an arXiv id / DOI — they live on the first page or two.
_METADATA_SCAN_CHARS = 20_000

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
            settings = get_settings()
            if source.kind == "paper" and settings.citation_lookup_enabled:
                text = "\n".join(seg[0] for seg in segments)[:_METADATA_SCAN_CHARS]
                citation = await fetch_citation(
                    source.filename, text, timeout=settings.citation_lookup_timeout
                )
                if citation:
                    source.cite_key, source.bibtex = citation
            source.status = "ready"
            source.chunk_count = len(chunks)
            await session.commit()
            logger.info("ingested source %s (%d chunks)", source_id, len(chunks))
        except Exception as exc:  # noqa: BLE001 — record any failure on the source row
            logger.exception("ingestion failed for source %s", source_id)
            source.status = "failed"
            source.error = str(exc)[:1000]
            await session.commit()


async def ingest_draft_file(file_id: uuid.UUID) -> None:
    """Re-embed a draft file's content so the agent can retrieve over the live draft.

    Best-effort: draft RAG staleness should never break editing, so failures only log.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        file = await session.get(ProjectFile, file_id)
    if file is None:
        return
    try:
        await qdrant.delete_draft_file(file.id)
        chunks = await run_in_threadpool(chunk_segments, [(file.content, {})])
        if chunks:
            vectors = await embed_texts([c["text"] for c in chunks])
            await qdrant.upsert_draft_chunks(
                file.project_id, file.id, file.path, chunks, vectors
            )
        logger.info("re-embedded draft file %s (%d chunks)", file_id, len(chunks))
    except Exception:  # noqa: BLE001 — draft indexing is best-effort
        logger.exception("draft ingestion failed for file %s", file_id)


async def cleanup_draft_file(file_id: uuid.UUID) -> None:
    """Best-effort removal of a deleted file's draft vectors."""
    try:
        await qdrant.delete_draft_file(file_id)
    except Exception:  # noqa: BLE001 — must not fail the delete request
        logger.exception("draft cleanup failed for file %s", file_id)
