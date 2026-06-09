import base64
import hashlib
import hmac
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from fastapi.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.core.aws import boto3_client
from app.core.exceptions import (
    AppError,
    AuthError,
    BadRequestError,
    ConflictError,
    ExternalServiceError,
)
from app.core.logging import get_logger

logger = get_logger("app.cognito")


class UserNotConfirmedError(AuthError):
    code = "user_not_confirmed"


# Maps Cognito error codes to application errors with safe, user-facing messages.
def _map_client_error(exc: ClientError) -> AppError:
    code = exc.response.get("Error", {}).get("Code", "")
    message = exc.response.get("Error", {}).get("Message", "Authentication error")
    mapping: dict[str, AppError] = {
        "UsernameExistsException": ConflictError("An account with this email already exists"),
        "CodeMismatchException": BadRequestError("Invalid verification code"),
        "ExpiredCodeException": BadRequestError("The verification code has expired"),
        "InvalidPasswordException": BadRequestError(message),
        "InvalidParameterException": BadRequestError(message),
        "UserNotConfirmedException": UserNotConfirmedError("Account is not confirmed yet"),
        "NotAuthorizedException": AuthError("Incorrect email or password"),
        "UserNotFoundException": AuthError("Incorrect email or password"),
        "LimitExceededException": BadRequestError("Too many attempts, please try again later"),
        "TooManyRequestsException": BadRequestError("Too many requests, please slow down"),
        "TooManyFailedAttemptsException": BadRequestError("Too many failed attempts"),
    }
    if code in mapping:
        return mapping[code]
    logger.error("unmapped Cognito error %s: %s", code, message)
    return ExternalServiceError("Authentication service error")


class CognitoService:
    """Thin async wrapper over the Cognito identity provider client.

    boto3 is synchronous, so each call is dispatched to a worker thread to avoid
    blocking the event loop.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        if not self.settings.cognito_client_id:
            logger.warning("Cognito client id is not configured; auth endpoints will fail")
        self._client = boto3_client("cognito-idp", self.settings)

    def _secret_hash(self, username: str) -> str | None:
        secret = self.settings.cognito_client_secret
        if not secret:
            return None
        digest = hmac.new(
            secret.encode("utf-8"),
            (username + self.settings.cognito_client_id).encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode()

    def _with_secret(self, username: str, params: dict[str, Any]) -> dict[str, Any]:
        secret_hash = self._secret_hash(username)
        if secret_hash:
            params["SecretHash"] = secret_hash
        return params

    async def _call(self, method: str, username: str, **params: Any) -> dict[str, Any]:
        fn = getattr(self._client, method)
        try:
            return await run_in_threadpool(fn, **self._with_secret(username, params))
        except ClientError as exc:
            raise _map_client_error(exc) from exc
        except BotoCoreError as exc:
            logger.error("Cognito transport error", exc_info=exc)
            raise ExternalServiceError("Authentication service unavailable") from exc

    async def sign_up(self, email: str, password: str) -> None:
        await self._call(
            "sign_up",
            email,
            ClientId=self.settings.cognito_client_id,
            Username=email,
            Password=password,
            UserAttributes=[{"Name": "email", "Value": email}],
        )

    async def confirm_sign_up(self, email: str, code: str) -> None:
        await self._call(
            "confirm_sign_up",
            email,
            ClientId=self.settings.cognito_client_id,
            Username=email,
            ConfirmationCode=code,
        )

    async def login(self, email: str, password: str) -> dict[str, Any]:
        auth_params = {"USERNAME": email, "PASSWORD": password}
        secret_hash = self._secret_hash(email)
        if secret_hash:
            auth_params["SECRET_HASH"] = secret_hash
        try:
            result = await run_in_threadpool(
                self._client.initiate_auth,
                ClientId=self.settings.cognito_client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters=auth_params,
            )
        except ClientError as exc:
            raise _map_client_error(exc) from exc
        except BotoCoreError as exc:
            logger.error("Cognito transport error", exc_info=exc)
            raise ExternalServiceError("Authentication service unavailable") from exc
        return result["AuthenticationResult"]

    async def forgot_password(self, email: str) -> None:
        await self._call(
            "forgot_password",
            email,
            ClientId=self.settings.cognito_client_id,
            Username=email,
        )

    async def confirm_forgot_password(self, email: str, code: str, new_password: str) -> None:
        await self._call(
            "confirm_forgot_password",
            email,
            ClientId=self.settings.cognito_client_id,
            Username=email,
            ConfirmationCode=code,
            Password=new_password,
        )

    async def change_password(
        self, access_token: str, old_password: str, new_password: str
    ) -> None:
        try:
            await run_in_threadpool(
                self._client.change_password,
                AccessToken=access_token,
                PreviousPassword=old_password,
                ProposedPassword=new_password,
            )
        except ClientError as exc:
            raise _map_client_error(exc) from exc

    async def delete_user(self, access_token: str) -> None:
        try:
            await run_in_threadpool(self._client.delete_user, AccessToken=access_token)
        except ClientError as exc:
            raise _map_client_error(exc) from exc


def get_cognito_service() -> CognitoService:
    return CognitoService()
