import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import AuthIdentity, resolve_identity
from app.db.session import get_session
from app.models.project import Project
from app.models.user import User
from app.services import projects as projects_service
from app.services import users

_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@dataclass
class CurrentUser:
    user: User
    token: str
    identity: AuthIdentity

    @property
    def is_guest(self) -> bool:
        return self.identity.kind == "guest"


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    if credentials is None:
        raise AuthError("Authentication required")

    token = credentials.credentials
    identity = await resolve_identity(token)

    if identity.kind == "guest":
        user = await users.get_user_by_id(session, uuid.UUID(identity.subject))
        if user is None or not user.is_guest:
            raise AuthError("Guest session is no longer valid")
    else:
        user = await users.get_or_create_cognito_user(session, identity.subject, identity.email)

    return CurrentUser(user=user, token=token, identity=identity)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_cognito_user(current: CurrentUserDep) -> CurrentUser:
    """Dependency for endpoints that act on a real Cognito account (not guests)."""
    if current.is_guest:
        raise ForbiddenError("This action is not available for guest sessions")
    return current


async def owned_project(
    project_id: uuid.UUID, session: SessionDep, current: CurrentUserDep
) -> Project:
    """Resolve a project owned by the current user (404 otherwise)."""
    return await projects_service.get_owned_project(session, project_id, current.user.id)


OwnedProject = Annotated[Project, Depends(owned_project)]
