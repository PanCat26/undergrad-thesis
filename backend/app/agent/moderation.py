from openai import AsyncOpenAI

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.moderation")


async def is_flagged(text: str) -> bool:
    """Return True if the text violates the OpenAI moderation policy.

    Fails open (returns False) on empty input or transient errors so a moderation
    hiccup never blocks the assistant.
    """
    settings = get_settings()
    if not text.strip() or not settings.openai_api_key:
        return False
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.moderations.create(model=settings.moderation_model, input=text)
        return bool(response.results[0].flagged)
    except Exception:  # noqa: BLE001 — never break chat on a moderation failure
        logger.exception("moderation check failed")
        return False
