from httpx import AsyncClient


async def _create_project(client: AsyncClient, auth: dict) -> str:
    resp = await client.post("/api/projects", headers=auth, json={"name": "Doc"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_new_project_seeds_main_tex(client: AsyncClient, guest_auth: dict) -> None:
    project_id = await _create_project(client, guest_auth)
    resp = await client.get(f"/api/projects/{project_id}/files", headers=guest_auth)
    assert resp.status_code == 200
    assert "main.tex" in [f["path"] for f in resp.json()]


async def test_file_crud_flow(client: AsyncClient, guest_auth: dict) -> None:
    project_id = await _create_project(client, guest_auth)

    created = await client.post(
        f"/api/projects/{project_id}/files",
        headers=guest_auth,
        json={"path": "chapters/intro.tex", "content": "hi"},
    )
    assert created.status_code == 201
    file_id = created.json()["id"]
    assert created.json()["content"] == "hi"

    duplicate = await client.post(
        f"/api/projects/{project_id}/files",
        headers=guest_auth,
        json={"path": "chapters/intro.tex"},
    )
    assert duplicate.status_code == 409

    fetched = await client.get(f"/api/projects/{project_id}/files/{file_id}", headers=guest_auth)
    assert fetched.json()["content"] == "hi"

    updated = await client.put(
        f"/api/projects/{project_id}/files/{file_id}",
        headers=guest_auth,
        json={"content": "bye"},
    )
    assert updated.json()["content"] == "bye"

    renamed = await client.patch(
        f"/api/projects/{project_id}/files/{file_id}",
        headers=guest_auth,
        json={"path": "chapters/intro2.tex"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["path"] == "chapters/intro2.tex"

    deleted = await client.delete(
        f"/api/projects/{project_id}/files/{file_id}", headers=guest_auth
    )
    assert deleted.status_code == 204


async def test_invalid_path_is_rejected(client: AsyncClient, guest_auth: dict) -> None:
    project_id = await _create_project(client, guest_auth)
    resp = await client.post(
        f"/api/projects/{project_id}/files",
        headers=guest_auth,
        json={"path": "../escape.tex"},
    )
    assert resp.status_code == 422


async def test_files_require_auth(client: AsyncClient, guest_auth: dict) -> None:
    project_id = await _create_project(client, guest_auth)
    resp = await client.get(f"/api/projects/{project_id}/files")
    assert resp.status_code == 401


async def test_files_isolated_per_user(client: AsyncClient, guest_auth: dict) -> None:
    project_id = await _create_project(client, guest_auth)
    other = await client.post("/api/auth/guest")
    other_auth = {"Authorization": f"Bearer {other.json()['access_token']}"}
    resp = await client.get(f"/api/projects/{project_id}/files", headers=other_auth)
    assert resp.status_code == 404
