from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Cognito subject + email are null for guest users.
    cognito_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Per-user chat model choice (registered users only). NULL ⇒ server default.
    # A base_url makes it a custom OpenAI-compatible endpoint (local/tunneled model).
    llm_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    llm_api_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    projects: Mapped[list["Project"]] = relationship(  # noqa: F821
        back_populates="owner", cascade="all, delete-orphan"
    )
