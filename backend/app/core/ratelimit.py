"""Abuse guardrails for the public, guest-accessible API.

Fixed-window counters protect the cost-bearing endpoints (chat/LLM, upload/embeddings, compile)
against a bot or malicious user — including **guest-token farming**, where someone mints many guest
identities to dodge per-identity limits. Defense in depth:

- per-identity **burst** + **daily** limits (guests capped far tighter than registered users),
- a per-IP throttle on guest-session creation, and
- a global **daily circuit breaker** that bounds the worst-case LLM bill no matter how many
  identities/IPs are involved.

The default backend is Postgres (`DbRateLimiter`) — durable across restarts and correct across
workers, reusing the database we already run. An `InMemoryRateLimiter` exists for scale-out-free
setups. Backend is chosen by `settings.rate_limit_backend`.
"""
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import RateLimitError
from app.models.rate_counter import RateCounter


@dataclass(frozen=True)
class ScopeLimits:
    window_seconds: int  # burst window
    guest_burst: int
    user_burst: int
    guest_daily: int
    user_daily: int


# Per-scope limits. Guests are capped far tighter than registered users.
LIMITS: dict[str, ScopeLimits] = {
    "chat": ScopeLimits(600, 8, 30, 30, 300),
    "upload": ScopeLimits(600, 5, 30, 20, 200),
    "compile": ScopeLimits(600, 15, 60, 60, 500),
}
_DAY_SECONDS = 86_400
GUEST_ISSUE_WINDOW = 3_600
GUEST_ISSUE_PER_IP = 10
_GLOBAL_KEY = "global:agent_runs"


def _bucket_key(key: str, window_seconds: int) -> str:
    """Append the current fixed-window bucket so each window gets its own counter row."""
    return f"{key}:{int(time.time()) // window_seconds}"


class RateLimiter(Protocol):
    async def hit(self, session: AsyncSession, key: str, window_seconds: int) -> int:
        """Increment the counter for `key`'s current window and return the new count."""
        ...


class DbRateLimiter:
    """Durable, atomic fixed-window counters in Postgres (or sqlite in tests)."""

    async def hit(self, session: AsyncSession, key: str, window_seconds: int) -> int:
        full_key = _bucket_key(key, window_seconds)
        expires_at = datetime.now(UTC) + timedelta(seconds=window_seconds)
        dialect = session.get_bind().dialect.name
        insert = pg_insert if dialect == "postgresql" else sqlite_insert
        stmt = insert(RateCounter).values(key=full_key, count=1, expires_at=expires_at)
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"], set_={"count": RateCounter.count + 1}
        )
        await session.execute(stmt)
        count = await session.scalar(select(RateCounter.count).where(RateCounter.key == full_key))
        await session.commit()
        return int(count or 0)


class InMemoryRateLimiter:
    """Process-local counters — for single-process dev or scale-out-free deployments."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def hit(self, session: AsyncSession, key: str, window_seconds: int) -> int:
        full_key = _bucket_key(key, window_seconds)
        self._counts[full_key] = self._counts.get(full_key, 0) + 1
        return self._counts[full_key]


_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        backend = get_settings().rate_limit_backend
        _limiter = InMemoryRateLimiter() if backend == "memory" else DbRateLimiter()
    return _limiter


async def enforce_scope(session: AsyncSession, scope: str, identity: str, is_guest: bool) -> None:
    """Enforce the per-identity burst + daily limits for a cost-bearing scope."""
    if not get_settings().rate_limit_enabled:
        return
    limits = LIMITS[scope]
    limiter = get_rate_limiter()
    burst = limits.guest_burst if is_guest else limits.user_burst
    if await limiter.hit(session, f"{scope}:burst:{identity}", limits.window_seconds) > burst:
        raise RateLimitError("You're doing that too quickly — please slow down and try again.")
    daily = limits.guest_daily if is_guest else limits.user_daily
    if await limiter.hit(session, f"{scope}:day:{identity}", _DAY_SECONDS) > daily:
        raise RateLimitError("You've reached today's usage limit for this action.")


async def enforce_global_budget(session: AsyncSession) -> None:
    """App-wide daily ceiling on agent runs — the backstop against distributed abuse."""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    runs = await get_rate_limiter().hit(session, _GLOBAL_KEY, _DAY_SECONDS)
    if runs > settings.global_daily_agent_runs:
        raise RateLimitError(
            "The assistant is temporarily unavailable due to high demand. Please try again later."
        )


async def enforce_guest_issuance(session: AsyncSession, ip: str) -> None:
    """Throttle guest-session creation per client IP to stop identity farming."""
    if not get_settings().rate_limit_enabled:
        return
    count = await get_rate_limiter().hit(session, f"guest_issue:{ip}", GUEST_ISSUE_WINDOW)
    if count > GUEST_ISSUE_PER_IP:
        raise RateLimitError("Too many guest sessions from this network. Please try again later.")
