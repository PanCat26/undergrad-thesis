import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.file import ProjectFile

DEFAULT_MAIN_TEX = r"""\documentclass{article}

\title{Untitled}
\author{}
\date{\today}

\begin{document}
\maketitle

\section{Introduction}
Start writing here.

\end{document}
"""


async def list_files(session: AsyncSession, project_id: uuid.UUID) -> list[ProjectFile]:
    result = await session.execute(
        select(ProjectFile)
        .where(ProjectFile.project_id == project_id)
        .order_by(ProjectFile.path)
    )
    return list(result.scalars().all())


async def get_file(
    session: AsyncSession, project_id: uuid.UUID, file_id: uuid.UUID
) -> ProjectFile:
    file = await session.get(ProjectFile, file_id)
    if file is None or file.project_id != project_id:
        raise NotFoundError("File not found")
    return file


async def _path_exists(session: AsyncSession, project_id: uuid.UUID, path: str) -> bool:
    result = await session.execute(
        select(ProjectFile.id).where(
            ProjectFile.project_id == project_id, ProjectFile.path == path
        )
    )
    return result.first() is not None


async def create_file(
    session: AsyncSession, project_id: uuid.UUID, path: str, content: str = ""
) -> ProjectFile:
    if await _path_exists(session, project_id, path):
        raise ConflictError("A file with this path already exists")
    file = ProjectFile(project_id=project_id, path=path, content=content)
    session.add(file)
    await session.commit()
    await session.refresh(file)
    return file


async def upsert_file(
    session: AsyncSession, project_id: uuid.UUID, path: str, content: str
) -> ProjectFile:
    """Create the file at `path`, or overwrite its content if it already exists."""
    result = await session.execute(
        select(ProjectFile).where(
            ProjectFile.project_id == project_id, ProjectFile.path == path
        )
    )
    file = result.scalar_one_or_none()
    if file is None:
        file = ProjectFile(project_id=project_id, path=path, content=content)
        session.add(file)
    else:
        file.content = content
    await session.commit()
    await session.refresh(file)
    return file


async def update_content(session: AsyncSession, file: ProjectFile, content: str) -> ProjectFile:
    file.content = content
    await session.commit()
    await session.refresh(file)
    return file


async def rename_file(session: AsyncSession, file: ProjectFile, new_path: str) -> ProjectFile:
    if new_path != file.path and await _path_exists(session, file.project_id, new_path):
        raise ConflictError("A file with this path already exists")
    file.path = new_path
    await session.commit()
    await session.refresh(file)
    return file


async def delete_file(session: AsyncSession, file: ProjectFile) -> None:
    await session.delete(file)
    await session.commit()


async def seed_default_files(session: AsyncSession, project_id: uuid.UUID) -> None:
    """Create the starter main.tex so a new project opens with a compilable document."""
    session.add(ProjectFile(project_id=project_id, path="main.tex", content=DEFAULT_MAIN_TEX))
    await session.commit()
