import time
from dataclasses import dataclass

import httpx
from jose import JWTError, jwt

from app.config import Settings, get_settings
from app.core.exceptions import AuthError
from app.core.logging import get_logger

logger = get_logger("app.security")

GUEST_ISSUER = "research-tool"
GUEST_ALGORITHM = "HS256"

_jwks_cache: dict[str, dict] = {}


@dataclass
class AuthIdentity:
    """Resolved identity from a bearer token."""

    kind: str  # "guest" | "cognito"
    subject: str  # guest -> local user id; cognito -> cognito sub
    email: str | None = None


def create_guest_token(user_id: str, settings: Settings | None = None) -> tuple[str, int]:
    """Create a signed guest token. Returns (token, expires_in_seconds)."""
    settings = settings or get_settings()
    ttl = settings.guest_token_ttl_minutes * 60
    now = int(time.time())
    claims = {
        "sub": user_id,
        "iss": GUEST_ISSUER,
        "token_use": "guest",
        "iat": now,
        "exp": now + ttl,
    }
    token = jwt.encode(claims, settings.guest_token_secret, algorithm=GUEST_ALGORITHM)
    return token, ttl


def _decode_guest_token(token: str, settings: Settings) -> AuthIdentity | None:
    try:
        claims = jwt.decode(
            token,
            settings.guest_token_secret,
            algorithms=[GUEST_ALGORITHM],
            issuer=GUEST_ISSUER,
        )
    except JWTError:
        return None
    if claims.get("token_use") != "guest":
        return None
    return AuthIdentity(kind="guest", subject=claims["sub"])


async def _fetch_jwks(settings: Settings) -> dict[str, dict]:
    if _jwks_cache:
        return _jwks_cache
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(settings.cognito_jwks_url)
        resp.raise_for_status()
    for key in resp.json().get("keys", []):
        _jwks_cache[key["kid"]] = key
    return _jwks_cache


async def _decode_cognito_token(token: str, settings: Settings) -> AuthIdentity | None:
    if not settings.cognito_user_pool_id:
        return None
    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        return None
    kid = header.get("kid")
    if not kid:
        return None

    keys = await _fetch_jwks(settings)
    key = keys.get(kid)
    if key is None:
        _jwks_cache.clear()
        keys = await _fetch_jwks(settings)
        key = keys.get(kid)
    if key is None:
        return None

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.cognito_issuer,
            options={"verify_aud": False},
        )
    except JWTError as exc:
        logger.info("cognito token rejected: %s", exc)
        return None

    if claims.get("token_use") != "access":
        return None
    if settings.cognito_client_id and claims.get("client_id") not in (
        settings.cognito_client_id,
        None,
    ):
        return None

    # Access tokens do not carry the email (it lives in the id token), and for
    # email-alias pools the "username" claim is an opaque UUID — so do not treat
    # it as the email. The real email is supplied at login time instead.
    return AuthIdentity(
        kind="cognito",
        subject=claims["sub"],
        email=claims.get("email"),
    )


async def resolve_identity(token: str, settings: Settings | None = None) -> AuthIdentity:
    """Resolve a bearer token to an identity, trying guest then Cognito."""
    settings = settings or get_settings()
    identity = _decode_guest_token(token, settings)
    if identity is not None:
        return identity
    identity = await _decode_cognito_token(token, settings)
    if identity is not None:
        return identity
    raise AuthError("Invalid or expired token")
