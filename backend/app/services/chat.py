import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.chat import ChatMessage, ChatSession


def derive_title(content: str) -> str:
    """A short chat title from the first user message."""
    text = " ".join(content.split())
    if len(text) > 40:
        return text[:40].rstrip() + "…"
    return text or "New chat"


async def list_sessions(session: AsyncSession, project_id: uuid.UUID) -> list[ChatSession]:
    result = await session.execute(
        select(ChatSession)
        .where(ChatSession.project_id == project_id)
        .order_by(ChatSession.created_at.desc())
    )
    return list(result.scalars().all())


async def create_session(
    session: AsyncSession, project_id: uuid.UUID, title: str, mode: str
) -> ChatSession:
    chat_session = ChatSession(project_id=project_id, title=title, mode=mode)
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)
    return chat_session


async def get_session(
    session: AsyncSession, project_id: uuid.UUID, session_id: uuid.UUID
) -> ChatSession:
    chat_session = await session.get(ChatSession, session_id)
    if chat_session is None or chat_session.project_id != project_id:
        raise NotFoundError("Chat session not found")
    return chat_session


async def update_session(
    session: AsyncSession,
    chat_session: ChatSession,
    *,
    title: str | None = None,
    mode: str | None = None,
) -> ChatSession:
    if title is not None:
        chat_session.title = title
    if mode is not None:
        chat_session.mode = mode
    await session.commit()
    await session.refresh(chat_session)
    return chat_session


async def delete_session(session: AsyncSession, chat_session: ChatSession) -> None:
    await session.delete(chat_session)
    await session.commit()


async def list_messages(session: AsyncSession, session_id: uuid.UUID) -> list[ChatMessage]:
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return list(result.scalars().all())


async def get_history(
    session: AsyncSession, session_id: uuid.UUID, limit: int
) -> list[tuple[str, str]]:
    """Most recent `limit` messages as (role, content) pairs, chronological order."""
    result = await session.execute(
        select(ChatMessage.role, ChatMessage.content)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    rows = list(result.all())
    return [(role, content) for role, content in reversed(rows)]


async def add_message(
    session: AsyncSession,
    session_id: uuid.UUID,
    role: str,
    content: str,
    citations: list | None = None,
) -> ChatMessage:
    message = ChatMessage(
        session_id=session_id, role=role, content=content, citations=citations
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message
