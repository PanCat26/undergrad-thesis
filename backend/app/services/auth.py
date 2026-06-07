from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_guest_token, resolve_identity
from app.models.user import User
from app.schemas.auth import TokenResponse, UserOut
from app.services import users
from app.services.cognito import CognitoService


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, is_guest=user.is_guest)


async def start_guest_session(session: AsyncSession) -> TokenResponse:
    user = await users.create_guest_user(session)
    token, expires_in = create_guest_token(str(user.id))
    return TokenResponse(access_token=token, expires_in=expires_in, user=_user_out(user))


async def login(
    session: AsyncSession, cognito: CognitoService, email: str, password: str
) -> TokenResponse:
    auth_result = await cognito.login(email, password)
    access_token = auth_result["AccessToken"]
    identity = await resolve_identity(access_token)
    # The typed login email is authoritative; the access token does not carry it.
    user = await users.get_or_create_cognito_user(session, identity.subject, email)
    return TokenResponse(
        access_token=access_token,
        expires_in=auth_result.get("ExpiresIn"),
        user=_user_out(user),
    )
