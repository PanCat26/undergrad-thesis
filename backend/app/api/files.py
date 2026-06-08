import uuid

from fastapi import APIRouter, Response, status
from fastapi.concurrency import run_in_threadpool

from app.api.deps import OwnedProject, SessionDep
from app.schemas.file import FileContentOut, FileCreate, FileOut, FileRename, FileUpdate
from app.services import files as files_service
from app.services import latex as latex_service

router = APIRouter(prefix="/projects/{project_id}", tags=["files"])


@router.get("/files", response_model=list[FileOut])
async def list_files(project: OwnedProject, session: SessionDep) -> list[FileOut]:
    files = await files_service.list_files(session, project.id)
    return [FileOut.model_validate(f) for f in files]


@router.post("/files", response_model=FileContentOut, status_code=status.HTTP_201_CREATED)
async def create_file(
    payload: FileCreate, project: OwnedProject, session: SessionDep
) -> FileContentOut:
    file = await files_service.create_file(session, project.id, payload.path, payload.content)
    return FileContentOut.model_validate(file)


@router.get("/files/{file_id}", response_model=FileContentOut)
async def get_file(
    file_id: uuid.UUID, project: OwnedProject, session: SessionDep
) -> FileContentOut:
    file = await files_service.get_file(session, project.id, file_id)
    return FileContentOut.model_validate(file)


@router.put("/files/{file_id}", response_model=FileContentOut)
async def update_file(
    file_id: uuid.UUID, payload: FileUpdate, project: OwnedProject, session: SessionDep
) -> FileContentOut:
    file = await files_service.get_file(session, project.id, file_id)
    file = await files_service.update_content(session, file, payload.content)
    return FileContentOut.model_validate(file)


@router.patch("/files/{file_id}", response_model=FileOut)
async def rename_file(
    file_id: uuid.UUID, payload: FileRename, project: OwnedProject, session: SessionDep
) -> FileOut:
    file = await files_service.get_file(session, project.id, file_id)
    file = await files_service.rename_file(session, file, payload.path)
    return FileOut.model_validate(file)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(file_id: uuid.UUID, project: OwnedProject, session: SessionDep) -> None:
    file = await files_service.get_file(session, project.id, file_id)
    await files_service.delete_file(session, file)


@router.post("/compile")
async def compile_project(project: OwnedProject, session: SessionDep) -> Response:
    files = await files_service.list_files(session, project.id)
    sources = [(f.path, f.content) for f in files]
    pdf = await run_in_threadpool(latex_service.compile_project, sources)
    return Response(content=pdf, media_type="application/pdf")
