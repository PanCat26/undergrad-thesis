from httpx import AsyncClient


async def test_guest_session_returns_token_and_user(client: AsyncClient) -> None:
    resp = await client.post("/api/auth/guest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["is_guest"] is True
    assert body["user"]["email"] is None


async def test_me_returns_current_guest(client: AsyncClient, guest_auth: dict) -> None:
    resp = await client.get("/api/auth/me", headers=guest_auth)
    assert resp.status_code == 200
    assert resp.json()["is_guest"] is True


async def test_me_requires_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_register_then_confirm(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/register", json={"email": "a@b.com", "password": "Passw0rd!"}
    )
    assert resp.status_code == 201

    bad = await client.post("/api/auth/confirm", json={"email": "a@b.com", "code": "000000"})
    assert bad.status_code == 400

    ok = await client.post("/api/auth/confirm", json={"email": "a@b.com", "code": "123456"})
    assert ok.status_code == 200


async def test_register_duplicate_is_conflict(client: AsyncClient) -> None:
    payload = {"email": "dup@b.com", "password": "Passw0rd!"}
    assert (await client.post("/api/auth/register", json=payload)).status_code == 201
    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


async def test_forgot_then_reset_password(client: AsyncClient) -> None:
    await client.post("/api/auth/forgot-password", json={"email": "x@y.com"})
    resp = await client.post(
        "/api/auth/reset-password",
        json={"email": "x@y.com", "code": "654321", "new_password": "NewPassw0rd!"},
    )
    assert resp.status_code == 200


async def test_change_password_forbidden_for_guest(client: AsyncClient, guest_auth: dict) -> None:
    resp = await client.post(
        "/api/auth/change-password",
        headers=guest_auth,
        json={"old_password": "x", "new_password": "Newpassw0rd!"},
    )
    assert resp.status_code == 403


async def test_delete_account_forbidden_for_guest(client: AsyncClient, guest_auth: dict) -> None:
    resp = await client.delete("/api/auth/account", headers=guest_auth)
    assert resp.status_code == 403


async def test_invalid_email_is_validation_error(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/register", json={"email": "not-an-email", "password": "Passw0rd!"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
