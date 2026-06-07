import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.project import ProjectCreate, ProjectOut, ProjectRename
from app.services import projects as projects_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(session: SessionDep, current: CurrentUserDep) -> list[ProjectOut]:
    items = await projects_service.list_projects(session, current.user.id)
    return [ProjectOut.model_validate(item) for item in items]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID, session: SessionDep, current: CurrentUserDep
) -> ProjectOut:
    project = await projects_service.get_owned_project(session, project_id, current.user.id)
    return ProjectOut.model_validate(project)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, session: SessionDep, current: CurrentUserDep
) -> ProjectOut:
    project = await projects_service.create_project(session, current.user.id, payload.name)
    return ProjectOut.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def rename_project(
    project_id: uuid.UUID,
    payload: ProjectRename,
    session: SessionDep,
    current: CurrentUserDep,
) -> ProjectOut:
    project = await projects_service.get_owned_project(session, project_id, current.user.id)
    project = await projects_service.rename_project(session, project, payload.name)
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID, session: SessionDep, current: CurrentUserDep
) -> None:
    project = await projects_service.get_owned_project(session, project_id, current.user.id)
    await projects_service.delete_project(session, project)
