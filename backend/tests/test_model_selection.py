from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.agent.llm import config_from_parts, resolve_llm_config
from app.api.auth import _llm_presets, _probe_error, _validate_custom_url
from app.config import get_settings
from app.core.exceptions import BadRequestError
from app.core.security import AuthIdentity

# --- Unit: config resolution ------------------------------------------------------------------


def test_config_from_parts_default() -> None:
    cfg = config_from_parts(None, None, None)
    settings = get_settings()
    assert cfg.model == settings.openai_model
    assert cfg.base_url is None
    assert cfg.api_key == settings.openai_api_key


def test_config_from_parts_custom_uses_placeholder_key() -> None:
    cfg = config_from_parts("llama3.1", "http://host.docker.internal:11434/v1", None)
    assert cfg.model == "llama3.1"
    assert cfg.base_url == "http://host.docker.internal:11434/v1"
    assert cfg.api_key == "not-needed"


def test_resolve_llm_config_from_user_custom() -> None:
    user = SimpleNamespace(llm_model="m", llm_base_url="http://x/v1", llm_api_key="k")
    cfg = resolve_llm_config(user)
    assert (cfg.model, cfg.base_url, cfg.api_key) == ("m", "http://x/v1", "k")


# --- Unit: validation + helpers ---------------------------------------------------------------


def test_validate_custom_url_rejects_metadata_ip() -> None:
    with pytest.raises(BadRequestError):
        _validate_custom_url("http://169.254.169.254/v1")


def test_validate_custom_url_rejects_bad_scheme() -> None:
    with pytest.raises(BadRequestError):
        _validate_custom_url("ftp://example.com/v1")


def test_validate_custom_url_accepts_host_gateway() -> None:
    _validate_custom_url("http://host.docker.internal:11434/v1")  # no raise


def test_presets_default_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "openai_alt_model", None)
    presets = _llm_presets()
    assert len(presets) == 1
    assert presets[0].id == get_settings().openai_model


def test_presets_includes_configured_alt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "openai_alt_model", "gpt-5-mini")
    monkeypatch.setattr(get_settings(), "openai_alt_label", "GPT-5 mini")
    presets = _llm_presets()
    assert [p.id for p in presets][1] == "gpt-5-mini"


def test_probe_error_maps_connection() -> None:
    assert "reach" in _probe_error(ConnectionError("refused")).lower()


# --- API ---------------------------------------------------------------------------------------


@pytest.fixture
def registered_auth(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Force any bearer token to resolve to a registered (Cognito) user."""

    async def fake_resolve(token: str, settings: object = None) -> AuthIdentity:
        return AuthIdentity(kind="cognito", subject="sub-1", email="reg@test.com")

    monkeypatch.setattr("app.api.deps.resolve_identity", fake_resolve)
    return {"Authorization": "Bearer reg"}


async def test_update_llm_custom_endpoint(client: AsyncClient, registered_auth: dict) -> None:
    resp = await client.patch(
        "/api/auth/me",
        headers=registered_auth,
        json={"model": "llama3.1", "base_url": "http://host.docker.internal:11434/v1"},
    )
    assert resp.status_code == 200
    assert resp.json()["llm_model"] == "llama3.1"
    me = await client.get("/api/auth/me", headers=registered_auth)
    assert me.json()["llm_base_url"].endswith("11434/v1")


async def test_update_llm_rejects_unknown_openai_model(
    client: AsyncClient, registered_auth: dict
) -> None:
    resp = await client.patch(
        "/api/auth/me", headers=registered_auth, json={"model": "gpt-evil", "base_url": None}
    )
    assert resp.status_code == 400


async def test_update_llm_default_clears(client: AsyncClient, registered_auth: dict) -> None:
    await client.patch(
        "/api/auth/me",
        headers=registered_auth,
        json={"model": "llama", "base_url": "http://host.docker.internal:11434/v1"},
    )
    resp = await client.patch(
        "/api/auth/me", headers=registered_auth, json={"model": None, "base_url": None}
    )
    assert resp.status_code == 200
    assert resp.json()["llm_model"] is None
    assert resp.json()["llm_base_url"] is None


async def test_update_llm_forbidden_for_guest(client: AsyncClient, guest_auth: dict) -> None:
    resp = await client.patch("/api/auth/me", headers=guest_auth, json={"model": None})
    assert resp.status_code == 403


async def test_llm_presets_endpoint(client: AsyncClient, guest_auth: dict) -> None:
    resp = await client.get("/api/auth/llm-presets", headers=guest_auth)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_llm_test_ok(
    client: AsyncClient, registered_auth: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeLLM:
        async def ainvoke(self, messages: object) -> str:
            return "ok"

    monkeypatch.setattr("app.api.auth.build_chat_openai", lambda *a, **k: FakeLLM())
    resp = await client.post(
        "/api/auth/llm-test",
        headers=registered_auth,
        json={"model": "llama", "base_url": "http://host.docker.internal:11434/v1"},
    )
    assert resp.json() == {"ok": True, "error": None}


async def test_llm_test_reports_failure(
    client: AsyncClient, registered_auth: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeLLM:
        async def ainvoke(self, messages: object) -> str:
            raise ConnectionError("refused")

    monkeypatch.setattr("app.api.auth.build_chat_openai", lambda *a, **k: FakeLLM())
    resp = await client.post(
        "/api/auth/llm-test",
        headers=registered_auth,
        json={"model": "llama", "base_url": "http://host.docker.internal:11434/v1"},
    )
    body = resp.json()
    assert body["ok"] is False
    assert "reach" in body["error"].lower()


async def test_llm_test_forbidden_for_guest(client: AsyncClient, guest_auth: dict) -> None:
    resp = await client.post("/api/auth/llm-test", headers=guest_auth, json={"model": "x"})
    assert resp.status_code == 403
