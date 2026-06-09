import uuid

from fastapi import APIRouter, BackgroundTasks, Response, status
from fastapi.concurrency import run_in_threadpool

from app.api.deps import OwnedProject, SessionDep
from app.rag.ingest import cleanup_draft_file, ingest_draft_file
from app.schemas.file import (
    FileApply,
    FileContentOut,
    FileCreate,
    FileOut,
    FileRename,
    FileUpdate,
)
from app.services import files as files_service
from app.services import latex as latex_service

router = APIRouter(prefix="/projects/{project_id}", tags=["files"])


@router.get("/files", response_model=list[FileOut])
async def list_files(project: OwnedProject, session: SessionDep) -> list[FileOut]:
    files = await files_service.list_files(session, project.id)
    return [FileOut.model_validate(f) for f in files]


@router.post("/files", response_model=FileContentOut, status_code=status.HTTP_201_CREATED)
async def create_file(
    payload: FileCreate,
    project: OwnedProject,
    session: SessionDep,
    background: BackgroundTasks,
) -> FileContentOut:
    file = await files_service.create_file(session, project.id, payload.path, payload.content)
    background.add_task(ingest_draft_file, file.id)
    return FileContentOut.model_validate(file)


@router.get("/files/{file_id}", response_model=FileContentOut)
async def get_file(
    file_id: uuid.UUID, project: OwnedProject, session: SessionDep
) -> FileContentOut:
    file = await files_service.get_file(session, project.id, file_id)
    return FileContentOut.model_validate(file)


@router.put("/files/{file_id}", response_model=FileContentOut)
async def update_file(
    file_id: uuid.UUID,
    payload: FileUpdate,
    project: OwnedProject,
    session: SessionDep,
    background: BackgroundTasks,
) -> FileContentOut:
    file = await files_service.get_file(session, project.id, file_id)
    file = await files_service.update_content(session, file, payload.content)
    background.add_task(ingest_draft_file, file.id)
    return FileContentOut.model_validate(file)


@router.patch("/files/{file_id}", response_model=FileOut)
async def rename_file(
    file_id: uuid.UUID,
    payload: FileRename,
    project: OwnedProject,
    session: SessionDep,
    background: BackgroundTasks,
) -> FileOut:
    file = await files_service.get_file(session, project.id, file_id)
    file = await files_service.rename_file(session, file, payload.path)
    background.add_task(ingest_draft_file, file.id)
    return FileOut.model_validate(file)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID,
    project: OwnedProject,
    session: SessionDep,
    background: BackgroundTasks,
) -> None:
    file = await files_service.get_file(session, project.id, file_id)
    removed_id = file.id
    await files_service.delete_file(session, file)
    background.add_task(cleanup_draft_file, removed_id)


@router.post("/files/apply", response_model=FileContentOut)
async def apply_file_edit(
    payload: FileApply,
    project: OwnedProject,
    session: SessionDep,
    background: BackgroundTasks,
) -> FileContentOut:
    """Apply an approved agent edit: create or overwrite the file, then re-embed the draft."""
    file = await files_service.upsert_file(session, project.id, payload.path, payload.content)
    background.add_task(ingest_draft_file, file.id)
    return FileContentOut.model_validate(file)


@router.post("/compile")
async def compile_project(project: OwnedProject, session: SessionDep) -> Response:
    files = await files_service.list_files(session, project.id)
    sources = [(f.path, f.content) for f in files]
    pdf = await run_in_threadpool(latex_service.compile_project, sources)
    return Response(content=pdf, media_type="application/pdf")
