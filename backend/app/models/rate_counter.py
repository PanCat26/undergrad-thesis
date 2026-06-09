from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RateCounter(Base):
    """A fixed-window counter backing the abuse guardrails.

    The window bucket is encoded in `key` (e.g. ``chat:burst:<id>:<bucket>``), so each window gets
    its own row; `expires_at` lets a periodic job purge stale rows. See app/core/ratelimit.py.
    """

    __tablename__ = "rate_counters"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
