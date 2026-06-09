import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    owner: Mapped["User"] = relationship(back_populates="projects")  # noqa: F821
    files: Mapped[list["ProjectFile"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
    sources: Mapped[list["Source"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["ChatSession"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
