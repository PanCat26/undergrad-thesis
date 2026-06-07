from typing import Any

from app.core.exceptions import BadRequestError, ConflictError


class FakeCognitoService:
    """In-memory stand-in for CognitoService used in tests.

    Records calls and simulates the few error cases the API depends on, without
    touching AWS. Token-issuing flows (login) are not exercised here because they
    require real Cognito-signed JWTs.
    """

    def __init__(self) -> None:
        self.signed_up: dict[str, str] = {}
        self.confirmed: set[str] = set()
        self.reset_codes: dict[str, str] = {}
        self.calls: list[tuple[str, tuple]] = []

    async def sign_up(self, email: str, password: str) -> None:
        self.calls.append(("sign_up", (email,)))
        if email in self.signed_up:
            raise ConflictError("An account with this email already exists")
        self.signed_up[email] = password

    async def confirm_sign_up(self, email: str, code: str) -> None:
        self.calls.append(("confirm_sign_up", (email, code)))
        if code != "123456":
            raise BadRequestError("Invalid verification code")
        self.confirmed.add(email)

    async def login(self, email: str, password: str) -> dict[str, Any]:
        self.calls.append(("login", (email,)))
        raise NotImplementedError("login is not simulated in tests")

    async def forgot_password(self, email: str) -> None:
        self.calls.append(("forgot_password", (email,)))
        self.reset_codes[email] = "654321"

    async def confirm_forgot_password(self, email: str, code: str, new_password: str) -> None:
        self.calls.append(("confirm_forgot_password", (email, code)))
        if code != "654321":
            raise BadRequestError("Invalid verification code")

    async def change_password(self, access_token: str, old: str, new: str) -> None:
        self.calls.append(("change_password", (access_token,)))

    async def delete_user(self, access_token: str) -> None:
        self.calls.append(("delete_user", (access_token,)))
