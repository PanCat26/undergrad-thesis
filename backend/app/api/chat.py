import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.agent.ask import run_agent
from app.agent.llm import resolve_llm_config
from app.agent.moderation import is_flagged
from app.api.deps import CurrentUserDep, OwnedProject, SessionDep, rate_limit
from app.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.schemas.chat import (
    MessageCreate,
    MessageOut,
    SessionCreate,
    SessionOut,
    SessionUpdate,
)
from app.services import chat as chat_service
from app.services import sources as sources_service

logger = get_logger("app.chat")
router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])

_MODERATION_REFUSAL = "I can't help with that request."


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(project: OwnedProject, session: SessionDep) -> list[SessionOut]:
    sessions = await chat_service.list_sessions(session, project.id)
    return [SessionOut.model_validate(s) for s in sessions]


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate, project: OwnedProject, session: SessionDep
) -> SessionOut:
    created = await chat_service.create_session(session, project.id, payload.title, payload.mode)
    return SessionOut.model_validate(created)


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: uuid.UUID, payload: SessionUpdate, project: OwnedProject, session: SessionDep
) -> SessionOut:
    chat_session = await chat_service.get_session(session, project.id, session_id)
    updated = await chat_service.update_session(
        session, chat_session, title=payload.title, mode=payload.mode
    )
    return SessionOut.model_validate(updated)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID, project: OwnedProject, session: SessionDep
) -> None:
    chat_session = await chat_service.get_session(session, project.id, session_id)
    await chat_service.delete_session(session, chat_session)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: uuid.UUID, project: OwnedProject, session: SessionDep
) -> list[MessageOut]:
    await chat_service.get_session(session, project.id, session_id)
    messages = await chat_service.list_messages(session, session_id)
    return [MessageOut.model_validate(m) for m in messages]


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    payload: MessageCreate,
    project: OwnedProject,
    session: SessionDep,
    current: CurrentUserDep,
    _rate_limited: Annotated[None, Depends(rate_limit("chat", global_budget=True))],
) -> StreamingResponse:
    settings = get_settings()
    chat_session = await chat_service.get_session(session, project.id, session_id)

    history = await chat_service.get_history(session, chat_session.id, settings.chat_history_limit)
    # Name the session after its first message (Claude-Code style).
    if not history:
        chat_session.title = chat_service.derive_title(payload.content)
    await chat_service.add_message(session, chat_session.id, "user", payload.content)

    source_names = [s.filename for s in await sources_service.list_sources(session, project.id)]
    session_id_value = chat_session.id
    mode = chat_session.mode
    # Per-user chat model (the user's own/custom endpoint, an OpenAI preset, or the server default).
    llm_config = resolve_llm_config(current.user)
    custom_model = llm_config.base_url is not None

    async def event_stream() -> AsyncIterator[str]:
        try:
            # Input moderation — refuse harmful requests before running the agent.
            if await is_flagged(payload.content):
                yield _sse({"type": "final", "content": _MODERATION_REFUSAL, "citations": []})
                async with get_sessionmaker()() as persist_session:
                    await chat_service.add_message(
                        persist_session, session_id_value, "assistant", _MODERATION_REFUSAL, []
                    )
                yield _sse({"type": "done"})
                return

            content = ""
            citations: list[dict] = []
            suppressed = False
            async for event in run_agent(
                project.id, payload.content, history, source_names, mode, llm_config
            ):
                if event["type"] == "final":
                    # Output moderation — replace flagged answers and drop their proposals.
                    if await is_flagged(event["content"]):
                        event = {"type": "final", "content": _MODERATION_REFUSAL, "citations": []}
                        suppressed = True
                    content = event["content"]
                    citations = event["citations"]
                    yield _sse(event)
                elif event["type"] == "proposed_edit":
                    if not suppressed:
                        yield _sse(event)
                else:
                    yield _sse(event)

            async with get_sessionmaker()() as persist_session:
                await chat_service.add_message(
                    persist_session, session_id_value, "assistant", content, citations
                )
            yield _sse({"type": "done"})
        except Exception:  # noqa: BLE001 — surface a clean error event to the client
            logger.exception("chat stream failed")
            # A custom model is the likely culprit when the user configured one; point them at it.
            message = (
                "Your selected model failed (it may be unreachable or incompatible). "
                "Check Settings → Model."
                if custom_model
                else "The assistant failed to respond."
            )
            yield _sse({"type": "error", "message": message})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
