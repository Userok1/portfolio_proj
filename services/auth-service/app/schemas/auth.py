from uuid import UUID

from pydantic import BaseModel, EmailStr


class RegisterIn(BaseModel):
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: UUID
    email: str


class IntrospectIn(BaseModel):
    token: str


class IntrospectOut(BaseModel):
    active: bool
    user_id: UUID | None = None
    email: str | None = None
