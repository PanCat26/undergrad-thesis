import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.project import Project
from app.services import files as files_service


async def list_projects(session: AsyncSession, owner_id: uuid.UUID) -> list[Project]:
    result = await session.execute(
        select(Project).where(Project.owner_id == owner_id).order_by(Project.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_project(session: AsyncSession, owner_id: uuid.UUID, name: str) -> Project:
    project = Project(owner_id=owner_id, name=name)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    await files_service.seed_default_files(session, project.id)
    return project


async def get_owned_project(
    session: AsyncSession, project_id: uuid.UUID, owner_id: uuid.UUID
) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.owner_id != owner_id:
        raise NotFoundError("Project not found")
    return project


async def rename_project(session: AsyncSession, project: Project, name: str) -> Project:
    project.name = name
    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(session: AsyncSession, project: Project) -> None:
    await session.delete(project)
    await session.commit()
