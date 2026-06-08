import os
import uuid

from fastapi import APIRouter, BackgroundTasks, File, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.api.deps import OwnedProject, SessionDep
from app.config import get_settings
from app.core.exceptions import BadRequestError
from app.rag import qdrant
from app.rag.extract import ALLOWED_EXTS, kind_for_ext
from app.rag.ingest import ingest_source
from app.schemas.source import SourceOut, SourcePreview
from app.services import sources as sources_service
from app.storage import get_storage

router = APIRouter(prefix="/projects/{project_id}/sources", tags=["sources"])

_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".json": "application/json",
    ".csv": "text/csv",
    ".tex": "text/plain; charset=utf-8",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("", response_model=list[SourceOut])
async def list_sources(project: OwnedProject, session: SessionDep) -> list[SourceOut]:
    sources = await sources_service.list_sources(session, project.id)
    return [SourceOut.model_validate(s) for s in sources]


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def upload_source(
    project: OwnedProject,
    session: SessionDep,
    background: BackgroundTasks,
    file: UploadFile = File(...),
) -> SourceOut:
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTS:
        raise BadRequestError("Unsupported file type. Allowed: pdf, docx, tex, csv, json")

    data = await file.read()
    if not data:
        raise BadRequestError("The uploaded file is empty")
    settings = get_settings()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise BadRequestError(f"File exceeds the {settings.max_upload_mb} MB limit")

    source_id = uuid.uuid4()
    storage_key = f"sources/{project.id}/{source_id}{ext}"
    await run_in_threadpool(get_storage().save, storage_key, data)

    source = await sources_service.create_source(
        session,
        project.id,
        source_id=source_id,
        filename=filename,
        ext=ext,
        kind=kind_for_ext(ext),
        storage_key=storage_key,
        size_bytes=len(data),
    )
    background.add_task(ingest_source, source.id)
    return SourceOut.model_validate(source)


@router.get("/{source_id}", response_model=SourceOut)
async def get_source(source_id: uuid.UUID, project: OwnedProject, session: SessionDep) -> SourceOut:
    source = await sources_service.get_source(session, project.id, source_id)
    return SourceOut.model_validate(source)


@router.get("/{source_id}/file")
async def get_source_file(
    source_id: uuid.UUID, project: OwnedProject, session: SessionDep
) -> Response:
    source = await sources_service.get_source(session, project.id, source_id)
    data = await run_in_threadpool(get_storage().read, source.storage_key)
    media_type = _MEDIA_TYPES.get(source.ext, "application/octet-stream")
    return Response(content=data, media_type=media_type)


@router.get("/{source_id}/preview", response_model=SourcePreview)
async def get_source_preview(
    source_id: uuid.UUID, project: OwnedProject, session: SessionDep
) -> SourcePreview:
    source = await sources_service.get_source(session, project.id, source_id)
    data = await run_in_threadpool(get_storage().read, source.storage_key)
    return await run_in_threadpool(sources_service.build_preview, data, source.ext)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID, project: OwnedProject, session: SessionDep
) -> None:
    source = await sources_service.get_source(session, project.id, source_id)
    await qdrant.delete_source(source.id)
    await run_in_threadpool(get_storage().delete, source.storage_key)
    await sources_service.delete_source_row(session, source)
