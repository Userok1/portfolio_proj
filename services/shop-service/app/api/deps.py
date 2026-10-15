from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import introspect_token
from ..db.session import SessionLocal

bearer = HTTPBearer(auto_error=False)


async def get_session() -> AsyncSession:
    async with SessionLocal() as s:
        yield s


async def get_user_id(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> UUID:
    from fastapi import HTTPException, status

    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    return await introspect_token(creds.credentials)


def get_idempotency_key(
    key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str | None:
    return key
