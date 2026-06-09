import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.db.session as db_session_module
from app.agent.ask import _build_tools
from app.models.source import Source


def _source(project_id: uuid.UUID, name: str, kind: str, **extra: object) -> Source:
    return Source(
        id=uuid.uuid4(),
        project_id=project_id,
        filename=name,
        kind=kind,
        ext="." + name.rsplit(".", 1)[-1],
        storage_key=f"k/{name}",
        size_bytes=1,
        status="ready",
        **extra,
    )


async def test_get_references_groups_papers_datasets_and_unknown(
    db_sessionmaker: async_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid.uuid4()
    async with db_sessionmaker() as session:
        session.add_all(
            [
                _source(
                    project_id,
                    "vit.pdf",
                    "paper",
                    cite_key="dosovitskiy2021image",
                    bibtex="@article{dosovitskiy2021image,\n  title={An Image is Worth 16x16}\n}",
                ),
                _source(project_id, "mystery.pdf", "paper"),  # no metadata found
                _source(project_id, "data.csv", "dataset"),
            ]
        )
        await session.commit()

    monkeypatch.setattr(db_session_module, "_sessionmaker", db_sessionmaker)
    edits = {"original": {}, "working": {}}
    tools = {t.name: t for t in _build_tools(project_id, [], edits, "agentic")}
    out = await tools["get_references"].ainvoke({})

    # Verified paper: full entry + filename→key mapping.
    assert "@article{dosovitskiy2021image" in out
    assert "vit.pdf -> \\cite{dosovitskiy2021image}" in out
    # Dataset guardrail: listed as not citable.
    assert "data.csv" in out
    assert "datasets" in out.lower()
    # Paper without metadata: flagged, not fabricated.
    assert "mystery.pdf" in out


async def test_get_references_available_in_ask_mode(
    db_sessionmaker: async_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid.uuid4()
    monkeypatch.setattr(db_session_module, "_sessionmaker", db_sessionmaker)
    edits = {"original": {}, "working": {}}
    tool_names = {t.name for t in _build_tools(project_id, [], edits, "qa")}
    assert "get_references" in tool_names
