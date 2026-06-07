from httpx import AsyncClient


async def test_projects_crud_flow(client: AsyncClient, guest_auth: dict) -> None:
    empty = await client.get("/api/projects", headers=guest_auth)
    assert empty.status_code == 200
    assert empty.json() == []

    created = await client.post("/api/projects", headers=guest_auth, json={"name": "Thesis"})
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "Thesis"
    project_id = project["id"]

    fetched = await client.get(f"/api/projects/{project_id}", headers=guest_auth)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == project_id

    listed = await client.get("/api/projects", headers=guest_auth)
    assert [p["id"] for p in listed.json()] == [project_id]

    renamed = await client.patch(
        f"/api/projects/{project_id}", headers=guest_auth, json={"name": "Thesis v2"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Thesis v2"

    deleted = await client.delete(f"/api/projects/{project_id}", headers=guest_auth)
    assert deleted.status_code == 204

    after = await client.get("/api/projects", headers=guest_auth)
    assert after.json() == []


async def test_projects_require_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/projects")
    assert resp.status_code == 401


async def test_missing_project_returns_404(client: AsyncClient, guest_auth: dict) -> None:
    resp = await client.patch(
        "/api/projects/00000000-0000-0000-0000-000000000000",
        headers=guest_auth,
        json={"name": "x"},
    )
    assert resp.status_code == 404


async def test_projects_are_isolated_per_user(client: AsyncClient, guest_auth: dict) -> None:
    # First guest creates a project.
    created = await client.post("/api/projects", headers=guest_auth, json={"name": "Owned"})
    project_id = created.json()["id"]

    # A second, independent guest must not see or touch it.
    other = await client.post("/api/auth/guest")
    other_auth = {"Authorization": f"Bearer {other.json()['access_token']}"}

    listed = await client.get("/api/projects", headers=other_auth)
    assert listed.json() == []

    forbidden = await client.delete(f"/api/projects/{project_id}", headers=other_auth)
    assert forbidden.status_code == 404
