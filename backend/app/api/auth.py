from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    CurrentUser,
    CurrentUserDep,
    GuestIssuanceThrottle,
    SessionDep,
    require_cognito_user,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    ConfirmRequest,
    ForgotPasswordRequest,
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
    return UserOut(id=current.user.id, email=current.user.email, is_guest=current.user.is_guest)
