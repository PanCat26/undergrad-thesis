from openai import AsyncOpenAI

from app.config import get_settings
from app.core.exceptions import ExternalServiceError

_BATCH_SIZE = 100


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with OpenAI, batching to stay within request limits."""
    if not texts:
        return []
    settings = get_settings()
    if not settings.openai_api_key:
        raise ExternalServiceError("OpenAI API key is not configured")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        response = await client.embeddings.create(
            model=settings.openai_embedding_model, input=batch
        )
        vectors.extend(item.embedding for item in response.data)
    return vectors
