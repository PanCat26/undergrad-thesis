"""Resolve and build the chat model for a request.

The chat model is per-user (registered users choose in Settings): the server default, a second
OpenAI preset, or a custom OpenAI-compatible endpoint (a local/tunneled model). Embeddings and
moderation are deliberately NOT affected — they always use the server's model/key.
"""
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.models.user import User

# ChatOpenAI requires a non-empty key; keyless local servers (e.g. Ollama) accept any value.
_PLACEHOLDER_KEY = "not-needed"


@dataclass(frozen=True)
class LlmConfig:
    model: str
    base_url: str | None = None
    api_key: str | None = None


def config_from_parts(model: str | None, base_url: str | None, api_key: str | None) -> LlmConfig:
    """Build a config from raw parts. A base_url ⇒ custom endpoint (keyless servers get a
    placeholder key); otherwise an OpenAI model on the server key."""
    settings = get_settings()
    if base_url:
        return LlmConfig(
            model=model or settings.openai_model,
            base_url=base_url,
            api_key=api_key or _PLACEHOLDER_KEY,
        )
    return LlmConfig(
        model=model or settings.openai_model, base_url=None, api_key=settings.openai_api_key
    )


def resolve_llm_config(user: User | None) -> LlmConfig:
    """Resolve a user's stored chat-model choice, falling back to the server default."""
    if user is None:
        return config_from_parts(None, None, None)
    return config_from_parts(user.llm_model, user.llm_base_url, user.llm_api_key)


def build_chat_openai(config: LlmConfig, **kwargs: Any) -> ChatOpenAI:
    """Build a ChatOpenAI from a resolved config plus call-specific kwargs (temperature/timeout)."""
    params: dict[str, Any] = {"model": config.model, "api_key": config.api_key, **kwargs}
    if config.base_url:
        params["base_url"] = config.base_url
    return ChatOpenAI(**params)
