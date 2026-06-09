import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings, get_settings
from app.core import ratelimit
from app.core.exceptions import RateLimitError

# --- Unit tests against the test DB (DbRateLimiter is the default backend) ---------------------


async def test_enforce_scope_burst_blocks_after_limit(
    db_sessionmaker: async_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(ratelimit.LIMITS, "chat", ratelimit.ScopeLimits(600, 2, 2, 100, 100))
    async with db_sessionmaker() as session:
        await ratelimit.enforce_scope(session, "chat", "u1", is_guest=True)
        await ratelimit.enforce_scope(session, "chat", "u1", is_guest=True)
        with pytest.raises(RateLimitError):
            await ratelimit.enforce_scope(session, "chat", "u1", is_guest=True)


async def test_enforce_scope_daily_quota_blocks(
    db_sessionmaker: async_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(ratelimit.LIMITS, "chat", ratelimit.ScopeLimits(600, 100, 100, 2, 100))
    async with db_sessionmaker() as session:
        await ratelimit.enforce_scope(session, "chat", "u2", is_guest=True)
        await ratelimit.enforce_scope(session, "chat", "u2", is_guest=True)
        with pytest.raises(RateLimitError):
            await ratelimit.enforce_scope(session, "chat", "u2", is_guest=True)


async def test_registered_users_get_higher_limits(
    db_sessionmaker: async_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(ratelimit.LIMITS, "chat", ratelimit.ScopeLimits(600, 1, 5, 100, 100))
    async with db_sessionmaker() as session:
        # A registered identity sails past the guest burst of 1.
        for _ in range(5):
            await ratelimit.enforce_scope(session, "chat", "reg", is_guest=False)
        with pytest.raises(RateLimitError):
            await ratelimit.enforce_scope(session, "chat", "reg", is_guest=False)


async def test_global_budget_circuit_breaker(
    db_sessionmaker: async_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "global_daily_agent_runs", 2)
    async with db_sessionmaker() as session:
        await ratelimit.enforce_global_budget(session)
        await ratelimit.enforce_global_budget(session)
        with pytest.raises(RateLimitError):
            await ratelimit.enforce_global_budget(session)


async def test_disabled_flag_bypasses_limits(
    db_sessionmaker: async_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", False)
    monkeypatch.setitem(ratelimit.LIMITS, "chat", ratelimit.ScopeLimits(600, 1, 1, 1, 1))
    async with db_sessionmaker() as session:
        for _ in range(10):  # would trip instantly if enforced
            await ratelimit.enforce_scope(session, "chat", "u3", is_guest=True)


# --- API tests ---------------------------------------------------------------------------------


async def test_guest_issuance_throttled_per_ip(client: AsyncClient) -> None:
    last = None
    for _ in range(ratelimit.GUEST_ISSUE_PER_IP + 1):
        last = await client.post("/api/auth/guest")
    assert last is not None
    assert last.status_code == 429
    assert last.json()["error"]["code"] == "rate_limited"


async def test_long_message_rejected(client: AsyncClient, guest_auth: dict) -> None:
    """The chat message size cap (MessageCreate.max_length) blocks oversized input up front."""
    pid = (await client.post("/api/projects", headers=guest_auth, json={"name": "P"})).json()["id"]
    created = await client.post(
        f"/api/projects/{pid}/chat/sessions",
        headers=guest_auth,
        json={"title": "C", "mode": "qa"},
    )
    sid = created.json()["id"]
    resp = await client.post(
        f"/api/projects/{pid}/chat/sessions/{sid}/messages",
        headers=guest_auth,
        json={"content": "x" * 8001},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


# --- Prod config validation --------------------------------------------------------------------

_PROD_BASE = {
    "app_env": "prod",
    "openai_api_key": "sk-test",
    "cognito_user_pool_id": "pool",
    "cognito_client_id": "client",
    "database_url": "postgresql+asyncpg://app:app@postgres:5432/app",
}


def test_prod_config_rejects_default_guest_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(**_PROD_BASE, guest_token_secret="change-me-in-prod")


def test_prod_config_rejects_localhost_db() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **{**_PROD_BASE, "database_url": "postgresql+asyncpg://app:app@localhost:5432/app"},
            guest_token_secret="a-strong-secret",
        )


def test_prod_config_accepts_valid_settings() -> None:
    settings = Settings(**_PROD_BASE, guest_token_secret="a-strong-unique-secret")
    assert settings.is_prod
