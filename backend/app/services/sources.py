import csv
import io
import json
import uuid

import docx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.source import Source
from app.schemas.source import SourcePreview

_TABLE_MAX_ROWS = 500


async def list_sources(session: AsyncSession, project_id: uuid.UUID) -> list[Source]:
    result = await session.execute(
        select(Source).where(Source.project_id == project_id).order_by(Source.created_at.desc())
    )
    return list(result.scalars().all())


async def get_source(
    session: AsyncSession, project_id: uuid.UUID, source_id: uuid.UUID
) -> Source:
    source = await session.get(Source, source_id)
    if source is None or source.project_id != project_id:
        raise NotFoundError("Source not found")
    return source


async def create_source(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    source_id: uuid.UUID,
    filename: str,
    ext: str,
    kind: str,
    storage_key: str,
    size_bytes: int,
) -> Source:
    source = Source(
        id=source_id,
        project_id=project_id,
        filename=filename,
        ext=ext,
        kind=kind,
        storage_key=storage_key,
        size_bytes=size_bytes,
        status="processing",
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def delete_source_row(session: AsyncSession, source: Source) -> None:
    await session.delete(source)
    await session.commit()


def build_preview(data: bytes, ext: str) -> SourcePreview:
    """Build a viewer-friendly representation for non-PDF sources."""
    ext = ext.lower()
    if ext == ".pdf":
        return SourcePreview(view="pdf")
    if ext == ".tex":
        return SourcePreview(view="text", text=data.decode("utf-8", errors="replace"))
    if ext == ".docx":
        document = docx.Document(io.BytesIO(data))
        text = "\n\n".join(p.text for p in document.paragraphs)
        return SourcePreview(view="text", text=text)
    if ext == ".csv":
        rows = list(csv.reader(io.StringIO(data.decode("utf-8", errors="replace"))))
        columns = rows[0] if rows else []
        return SourcePreview(view="table", columns=columns, rows=rows[1 : _TABLE_MAX_ROWS + 1])
    if ext == ".json":
        try:
            parsed = json.loads(data.decode("utf-8", errors="replace"))
            text = json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            text = data.decode("utf-8", errors="replace")
        return SourcePreview(view="json", text=text)
    return SourcePreview(view="text", text="")
