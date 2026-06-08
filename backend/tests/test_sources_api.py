from pathlib import Path

import pytest
from httpx import AsyncClient

from app.storage.base import LocalDiskStorage


@pytest.fixture
def sources_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Mock out ingestion, blob storage, and Qdrant so the API tests need no network."""

    async def _noop(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.api.sources.ingest_source", _noop)
    monkeypatch.setattr("app.api.sources.get_storage", lambda: LocalDiskStorage(str(tmp_path)))
    monkeypatch.setattr("app.rag.qdrant.delete_source", _noop)


async def _project(client: AsyncClient, auth: dict) -> str:
    resp = await client.post("/api/projects", headers=auth, json={"name": "P"})
    return resp.json()["id"]


async def _upload(client: AsyncClient, auth: dict, project_id: str, name: str, data: bytes) -> dict:
    return (
        await client.post(
            f"/api/projects/{project_id}/sources",
            headers=auth,
            files={"file": (name, data, "application/octet-stream")},
        )
    ).json()


async def test_upload_creates_processing_source(
    client: AsyncClient, guest_auth: dict, sources_env: None
) -> None:
    pid = await _project(client, guest_auth)
    resp = await client.post(
        f"/api/projects/{pid}/sources",
        headers=guest_auth,
        files={"file": ("notes.tex", b"\\documentclass{article}", "text/plain")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "notes.tex"
    assert body["kind"] == "paper"
    assert body["status"] == "processing"


async def test_upload_rejects_unsupported_type(
    client: AsyncClient, guest_auth: dict, sources_env: None
) -> None:
    pid = await _project(client, guest_auth)
    resp = await client.post(
        f"/api/projects/{pid}/sources",
        headers=guest_auth,
        files={"file": ("malware.exe", b"MZ", "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_request"


async def test_list_and_delete_source(
    client: AsyncClient, guest_auth: dict, sources_env: None
) -> None:
    pid = await _project(client, guest_auth)
    created = await _upload(client, guest_auth, pid, "data.csv", b"a,b\n1,2")
    assert created["kind"] == "dataset"

    listed = await client.get(f"/api/projects/{pid}/sources", headers=guest_auth)
    assert [s["id"] for s in listed.json()] == [created["id"]]

    deleted = await client.delete(
        f"/api/projects/{pid}/sources/{created['id']}", headers=guest_auth
    )
    assert deleted.status_code == 204
    after = await client.get(f"/api/projects/{pid}/sources", headers=guest_auth)
    assert after.json() == []


async def test_preview_text_and_table(
    client: AsyncClient, guest_auth: dict, sources_env: None
) -> None:
    pid = await _project(client, guest_auth)
    tex = await _upload(client, guest_auth, pid, "a.tex", b"hello tex")
    csv = await _upload(client, guest_auth, pid, "a.csv", b"x,y\n1,2")

    tex_preview = await client.get(
        f"/api/projects/{pid}/sources/{tex['id']}/preview", headers=guest_auth
    )
    assert tex_preview.json()["view"] == "text"
    assert "hello tex" in tex_preview.json()["text"]

    csv_preview = await client.get(
        f"/api/projects/{pid}/sources/{csv['id']}/preview", headers=guest_auth
    )
    assert csv_preview.json()["view"] == "table"
    assert csv_preview.json()["columns"] == ["x", "y"]


async def test_source_file_endpoint(
    client: AsyncClient, guest_auth: dict, sources_env: None
) -> None:
    pid = await _project(client, guest_auth)
    src = await _upload(client, guest_auth, pid, "a.tex", b"raw bytes")
    resp = await client.get(f"/api/projects/{pid}/sources/{src['id']}/file", headers=guest_auth)
    assert resp.status_code == 200
    assert resp.content == b"raw bytes"


async def test_sources_require_auth(client: AsyncClient, guest_auth: dict) -> None:
    pid = await _project(client, guest_auth)
    resp = await client.get(f"/api/projects/{pid}/sources")
    assert resp.status_code == 401


async def test_sources_isolated_per_user(
    client: AsyncClient, guest_auth: dict, sources_env: None
) -> None:
    pid = await _project(client, guest_auth)
    other = await client.post("/api/auth/guest")
    other_auth = {"Authorization": f"Bearer {other.json()['access_token']}"}
    resp = await client.get(f"/api/projects/{pid}/sources", headers=other_auth)
    assert resp.status_code == 404
