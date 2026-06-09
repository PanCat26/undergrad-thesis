import json

import pytest
from httpx import AsyncClient


def _events(body: str) -> list[dict]:
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


async def _project(client: AsyncClient, auth: dict) -> str:
    return (await client.post("/api/projects", headers=auth, json={"name": "P"})).json()["id"]


async def _session(client: AsyncClient, auth: dict, pid: str) -> str:
    resp = await client.post(
        f"/api/projects/{pid}/chat/sessions", headers=auth, json={"title": "Chat"}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_session_crud_and_isolation(client: AsyncClient, guest_auth: dict) -> None:
    pid = await _project(client, guest_auth)
    sid = await _session(client, guest_auth, pid)

    listed = await client.get(f"/api/projects/{pid}/chat/sessions", headers=guest_auth)
    assert [s["id"] for s in listed.json()] == [sid]

    other = await client.post("/api/auth/guest")
    other_auth = {"Authorization": f"Bearer {other.json()['access_token']}"}
    forbidden = await client.delete(
        f"/api/projects/{pid}/chat/sessions/{sid}", headers=other_auth
    )
    assert forbidden.status_code == 404

    deleted = await client.delete(
        f"/api/projects/{pid}/chat/sessions/{sid}", headers=guest_auth
    )
    assert deleted.status_code == 204


async def test_message_streams_with_tool_calls_and_persists(
    client: AsyncClient, guest_auth: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run_agent(project_id, query, history, source_names=(), mode="qa"):  # noqa: ANN001
        yield {"type": "tool_call", "summary": 'Searched sources: "method"'}
        yield {"type": "token", "text": "Grounded "}
        yield {"type": "token", "text": "answer [1]"}
        yield {
            "type": "final",
            "content": "Grounded answer [1]",
            "citations": [
                {"index": 1, "kind": "source", "filename": "a.pdf", "loc": {"page": 1},
                 "source_id": "s1", "file_id": None}
            ],
        }

    monkeypatch.setattr("app.api.chat.run_agent", fake_run_agent)

    pid = await _project(client, guest_auth)
    sid = await _session(client, guest_auth, pid)

    resp = await client.post(
        f"/api/projects/{pid}/chat/sessions/{sid}/messages",
        headers=guest_auth,
        json={"content": "What is the method?"},
    )
    assert resp.status_code == 200

    # The session is renamed after its first message.
    sessions = await client.get(f"/api/projects/{pid}/chat/sessions", headers=guest_auth)
    assert sessions.json()[0]["title"] == "What is the method?"

    events = _events(resp.text)
    types = [e["type"] for e in events]
    assert types[0] == "tool_call"
    assert "final" in types
    assert types[-1] == "done"

    final = next(e for e in events if e["type"] == "final")
    assert final["citations"][0]["filename"] == "a.pdf"
    assert final["content"] == "Grounded answer [1]"

    history = await client.get(
        f"/api/projects/{pid}/chat/sessions/{sid}/messages", headers=guest_auth
    )
    roles = [m["role"] for m in history.json()]
    assert roles == ["user", "assistant"]
    assert history.json()[1]["content"] == "Grounded answer [1]"


async def test_message_abstention_has_no_citations(
    client: AsyncClient, guest_auth: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run_agent(project_id, query, history, source_names=(), mode="qa"):  # noqa: ANN001
        yield {"type": "token", "text": "I don't have enough information in the sources."}
        yield {
            "type": "final",
            "content": "I don't have enough information in the sources.",
            "citations": [],
        }

    monkeypatch.setattr("app.api.chat.run_agent", fake_run_agent)

    pid = await _project(client, guest_auth)
    sid = await _session(client, guest_auth, pid)
    resp = await client.post(
        f"/api/projects/{pid}/chat/sessions/{sid}/messages",
        headers=guest_auth,
        json={"content": "Unrelated question?"},
    )
    events = _events(resp.text)
    final = next(e for e in events if e["type"] == "final")
    assert final["citations"] == []
    assert "enough" in final["content"].lower()


async def test_patch_session_mode(client: AsyncClient, guest_auth: dict) -> None:
    pid = await _project(client, guest_auth)
    sid = await _session(client, guest_auth, pid)
    resp = await client.patch(
        f"/api/projects/{pid}/chat/sessions/{sid}", headers=guest_auth, json={"mode": "agentic"}
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "agentic"


async def test_input_moderation_refuses(
    client: AsyncClient, guest_auth: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_flag(text):  # noqa: ANN001
        return "BADWORD" in text

    monkeypatch.setattr("app.api.chat.is_flagged", fake_flag)
    pid = await _project(client, guest_auth)
    sid = await _session(client, guest_auth, pid)
    resp = await client.post(
        f"/api/projects/{pid}/chat/sessions/{sid}/messages",
        headers=guest_auth,
        json={"content": "BADWORD please"},
    )
    events = _events(resp.text)
    assert [e["type"] for e in events] == ["final", "done"]
    assert "can't help" in events[0]["content"].lower()


async def test_output_moderation_replaces_and_suppresses_edits(
    client: AsyncClient, guest_auth: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_flag(text):  # noqa: ANN001
        return "TOXIC" in text

    async def fake_run_agent(project_id, query, history, source_names=(), mode="qa"):  # noqa: ANN001
        yield {"type": "final", "content": "TOXIC content", "citations": [{"index": 1}]}
        yield {"type": "proposed_edit", "path": "main.tex", "diff": "@@", "content": "x"}

    monkeypatch.setattr("app.api.chat.is_flagged", fake_flag)
    monkeypatch.setattr("app.api.chat.run_agent", fake_run_agent)

    pid = await _project(client, guest_auth)
    sid = await _session(client, guest_auth, pid)
    resp = await client.post(
        f"/api/projects/{pid}/chat/sessions/{sid}/messages",
        headers=guest_auth,
        json={"content": "hello"},
    )
    events = _events(resp.text)
    final = next(e for e in events if e["type"] == "final")
    assert "can't help" in final["content"].lower()
    assert final["citations"] == []
    assert not any(e["type"] == "proposed_edit" for e in events)


async def test_agent_mode_forwards_proposed_edits(
    client: AsyncClient, guest_auth: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run_agent(project_id, query, history, source_names=(), mode="qa"):  # noqa: ANN001
        yield {"type": "final", "content": "Added a section.", "citations": []}
        yield {"type": "proposed_edit", "path": "main.tex", "diff": "@@ -1 +1", "content": "new"}

    monkeypatch.setattr("app.api.chat.run_agent", fake_run_agent)

    pid = await _project(client, guest_auth)
    sid = await _session(client, guest_auth, pid)
    resp = await client.post(
        f"/api/projects/{pid}/chat/sessions/{sid}/messages",
        headers=guest_auth,
        json={"content": "add a section"},
    )
    edits = [e for e in _events(resp.text) if e["type"] == "proposed_edit"]
    assert len(edits) == 1
    assert edits[0]["path"] == "main.tex"
    assert edits[0]["content"] == "new"
