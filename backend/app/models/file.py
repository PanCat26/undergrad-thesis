import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class ProjectFile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "project_files"
    __table_args__ = (UniqueConstraint("project_id", "path", name="uq_project_files_project_path"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Relative POSIX path within the project, e.g. "main.tex" or "chapters/intro.tex".
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    project: Mapped["Project"] = relationship(back_populates="files")  # noqa: F821
