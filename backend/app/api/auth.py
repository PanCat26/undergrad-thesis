from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, status
from langchain_core.messages import HumanMessage

from app.agent.llm import build_chat_openai, config_from_parts
from app.api.deps import (
    CurrentUser,
    CurrentUserDep,
    GuestIssuanceThrottle,
    SessionDep,
    require_cognito_user,
)
from app.config import get_settings
from app.core.exceptions import BadRequestError
from app.schemas.auth import (
    ChangePasswordRequest,
    ConfirmRequest,
    ForgotPasswordRequest,
    LlmPreset,
    LlmTestResult,
    LlmUpdate,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from app.services import auth as auth_service
from app.services import users as users_service
from app.services.cognito import CognitoService, get_cognito_service

router = APIRouter(prefix="/auth", tags=["auth"])

CognitoDep = Annotated[CognitoService, Depends(get_cognito_service)]
RegisteredUser = Annotated[CurrentUser, Depends(require_cognito_user)]

# A custom endpoint host that should never be a model server (cloud instance metadata).
_BLOCKED_HOST = "169.254.169.254"


def _llm_presets() -> list[LlmPreset]:
    settings = get_settings()
    presets = [LlmPreset(id=settings.openai_model, label=f"{settings.openai_model} (default)")]
    if settings.openai_alt_model:
        presets.append(LlmPreset(id=settings.openai_alt_model, label=settings.openai_alt_label))
    return presets


def _validate_custom_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise BadRequestError("Endpoint URL must be a valid http(s) URL")
    if parsed.hostname == _BLOCKED_HOST:
        raise BadRequestError("That endpoint host is not allowed")


def _probe_error(exc: Exception) -> str:
    name = exc.__class__.__name__
    text = str(exc)
    if "Connection" in name:
        return "Couldn't reach the endpoint (connection refused or DNS failure)."
    if "Timeout" in name:
        return "The endpoint timed out."
    if "Authentication" in name or "401" in text:
        return "The endpoint rejected the API key."
    if "NotFound" in name or "404" in text:
        return "The model was not found at that endpoint."
    return f"{name}: {text[:200]}"


@router.post("/guest", response_model=TokenResponse)
async def guest(session: SessionDep, _throttle: GuestIssuanceThrottle) -> TokenResponse:
    return await auth_service.start_guest_session(session)


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, cognito: CognitoDep) -> MessageResponse:
    await cognito.sign_up(payload.email, payload.password)
    return MessageResponse(message="A confirmation code has been sent to your email")


@router.post("/confirm", response_model=MessageResponse)
async def confirm(payload: ConfirmRequest, cognito: CognitoDep) -> MessageResponse:
    await cognito.confirm_sign_up(payload.email, payload.code)
    return MessageResponse(message="Your account has been confirmed, you can now log in")


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SessionDep, cognito: CognitoDep) -> TokenResponse:
    return await auth_service.login(session, cognito, payload.email, payload.password)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest, cognito: CognitoDep) -> MessageResponse:
    await cognito.forgot_password(payload.email)
    return MessageResponse(message="If the account exists, a reset code has been sent")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, cognito: CognitoDep) -> MessageResponse:
    await cognito.confirm_forgot_password(payload.email, payload.code, payload.new_password)
    return MessageResponse(message="Your password has been reset, you can now log in")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    cognito: CognitoDep,
    current: Annotated[CurrentUser, Depends(require_cognito_user)],
) -> MessageResponse:
    await cognito.change_password(current.token, payload.old_password, payload.new_password)
    return MessageResponse(message="Your password has been changed")


@router.delete("/account", response_model=MessageResponse)
async def delete_account(
    session: SessionDep,
    cognito: CognitoDep,
    current: Annotated[CurrentUser, Depends(require_cognito_user)],
) -> MessageResponse:
    await cognito.delete_user(current.token)
    await users_service.delete_user(session, current.user)
    return MessageResponse(message="Your account has been deleted")


@router.get("/me", response_model=UserOut)
async def me(current: CurrentUserDep) -> UserOut:
    return UserOut.model_validate(current.user)


@router.get("/llm-presets", response_model=list[LlmPreset])
async def llm_presets(_: CurrentUserDep) -> list[LlmPreset]:
    return _llm_presets()


@router.patch("/me", response_model=UserOut)
async def update_llm(payload: LlmUpdate, session: SessionDep, current: RegisteredUser) -> UserOut:
    """Set the user's chat model (registered users only)."""
    user = current.user
    base_url = (payload.base_url or "").strip() or None
    model = (payload.model or "").strip() or None
    if base_url:
        _validate_custom_url(base_url)
        if not model:
            raise BadRequestError("A model name is required for a custom endpoint")
        user.llm_model, user.llm_base_url = model, base_url
        user.llm_api_key = (payload.api_key or "").strip() or None
    else:
        if model is not None and model not in {p.id for p in _llm_presets()}:
            raise BadRequestError("Unknown model")
        user.llm_model, user.llm_base_url, user.llm_api_key = model, None, None
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.post("/llm-test", response_model=LlmTestResult)
async def llm_test(payload: LlmUpdate, _: RegisteredUser) -> LlmTestResult:
    """Probe a model config with a tiny completion so the user can verify it before use."""
    base_url = (payload.base_url or "").strip() or None
    if base_url:
        _validate_custom_url(base_url)
    config = config_from_parts(
        (payload.model or "").strip() or None, base_url, (payload.api_key or "").strip() or None
    )
    try:
        llm = build_chat_openai(config, temperature=0, max_tokens=1, timeout=15)
        await llm.ainvoke([HumanMessage(content="ping")])
        return LlmTestResult(ok=True)
    except Exception as exc:  # noqa: BLE001 — report a friendly reason, never 500
        return LlmTestResult(ok=False, error=_probe_error(exc))
