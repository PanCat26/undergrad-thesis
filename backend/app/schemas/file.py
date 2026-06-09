import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _clean_relative_path(value: str) -> str:
    """Normalise and validate a project-relative file path.

    Rejects absolute paths and any traversal so a path can never escape the
    project directory when materialised to disk for compilation.
    """
    path = value.strip().replace("\\", "/")
    if not path:
        raise ValueError("Path cannot be empty")
    if path.startswith("/"):
        raise ValueError("Path must be relative")
    segments = path.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise ValueError("Path contains an invalid segment")
    return "/".join(segments)


RelativePath = Annotated[str, AfterValidator(_clean_relative_path), Field(max_length=512)]


class FileCreate(BaseModel):
    path: RelativePath
    content: str = ""


class FileRename(BaseModel):
    path: RelativePath


class FileUpdate(BaseModel):
    content: str


class FileApply(BaseModel):
    path: RelativePath
    content: str


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    path: str
    updated_at: datetime


class FileContentOut(FileOut):
    content: str
