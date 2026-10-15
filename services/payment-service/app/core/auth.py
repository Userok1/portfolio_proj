from uuid import UUID

import httpx
from fastapi import HTTPException, status

from .config import settings


async def introspect_token(token: str) -> UUID:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.post(settings.AUTH_INTROSPECT_URL, json={"token": token})
            r.raise_for_status()
            data = r.json()
    except Exception:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "auth unavailable")
    if not data.get("active"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    return UUID(data["user_id"])
