import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class ConfirmRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=1, max_length=16)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=1, max_length=16)
    new_password: str = Field(min_length=8, max_length=256)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    is_guest: bool
    # Current chat-model choice; null base_url ⇒ an OpenAI preset (or the default).
    llm_model: str | None = None
    llm_base_url: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int | None = None
    user: UserOut


class MessageResponse(BaseModel):
    message: str


class LlmPreset(BaseModel):
    """A selectable OpenAI chat model (uses the server key)."""

    id: str
    label: str


class LlmUpdate(BaseModel):
    """Set the user's chat model. All-null ⇒ server default. A base_url ⇒ custom endpoint."""

    model: str | None = Field(default=None, max_length=255)
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=512)


class LlmTestResult(BaseModel):
    ok: bool
    error: str | None = None
