import uuid

import pytest

from app.core.exceptions import AuthError
from app.core.security import create_guest_token, resolve_identity


async def test_guest_token_roundtrip() -> None:
    user_id = str(uuid.uuid4())
    token, expires_in = create_guest_token(user_id)
    assert expires_in > 0

    identity = await resolve_identity(token)
    assert identity.kind == "guest"
    assert identity.subject == user_id


async def test_invalid_token_is_rejected() -> None:
    with pytest.raises(AuthError):
        await resolve_identity("not-a-real-token")
