from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.db.session as db_session_module
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.services.cognito import get_cognito_service
from tests.fakes import FakeCognitoService


@pytest_asyncio.fixture
async def db_sessionmaker() -> AsyncGenerator[async_sessionmaker, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    await engine.dispose()


@pytest.fixture
def fake_cognito() -> FakeCognitoService:
    return FakeCognitoService()


@pytest.fixture(autouse=True)
def _no_draft_ingest(monkeypatch: pytest.MonkeyPatch) -> None:
    """Draft re-embedding (OpenAI + Qdrant) is verified live, not in unit tests."""

    async def _noop(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.api.files.ingest_draft_file", _noop)
    monkeypatch.setattr("app.api.files.cleanup_draft_file", _noop)


@pytest_asyncio.fixture
async def client(
    db_sessionmaker: async_sessionmaker, fake_cognito: FakeCognitoService
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_session() -> AsyncGenerator:
        async with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_cognito_service] = lambda: fake_cognito

    # Background tasks and the SSE stream open their own sessions via the global
    # sessionmaker; point it at the test database for the duration of the test.
    previous_sessionmaker = db_session_module._sessionmaker
    db_session_module._sessionmaker = db_sessionmaker

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as http_client:
            yield http_client
    finally:
        db_session_module._sessionmaker = previous_sessionmaker


@pytest_asyncio.fixture
async def guest_auth(client: AsyncClient) -> dict[str, str]:
    resp = await client.post("/api/auth/guest")
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
