import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    kind: str
    ext: str
    size_bytes: int
    status: str
    error: str | None
    chunk_count: int | None
    created_at: datetime
    updated_at: datetime


class SourcePreview(BaseModel):
    view: Literal["pdf", "text", "table", "json"]
    text: str | None = None
    columns: list[str] | None = None
    rows: list[list[str]] | None = None
