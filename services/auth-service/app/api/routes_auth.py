from datetime import datetime, timedelta, timezone
import json
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import get_session
from ..core.rabbit import publish_event
from ..core.security import (
    create_access_token,
    decode_token,
    hash_password,
    new_refresh_jti,
    verify_password,
)
from ..db.models import RefreshSession, User
from ..schemas.auth import (
    IntrospectIn,
    IntrospectOut,
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenPair,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_pair(session: AsyncSession, user: User) -> TokenPair:
    access = create_access_token(str(user.id), user.email)
    jti = new_refresh_jti()
    rs = RefreshSession(
        jti=jti,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        revoked=False,
    )
    session.add(rs)
    await session.commit()
    return TokenPair(access_token=access, refresh_token=jti)


@router.post("/register", response_model=TokenPair, status_code=201)
async def register(data: RegisterIn, session: Annotated[AsyncSession, Depends(get_session)]):
    exists = (await session.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "email taken")
    user = User(email=data.email, password_hash=hash_password(data.password))
    session.add(user)
    await session.flush()
    pair = await _issue_pair(session, user)

    await publish_event(
        "user.registered",
        json.dumps({"type": "user.registered", "user_id": str(user.id), "email": user.email}).encode(),
    )
    return pair


@router.post("/login", response_model=TokenPair)
async def login(data: LoginIn, session: Annotated[AsyncSession, Depends(get_session)]):
    user = (await session.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad credentials")
    return await _issue_pair(session, user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshIn, session: Annotated[AsyncSession, Depends(get_session)]):
    rs = await session.get(RefreshSession, data.refresh_token)
    if not rs or rs.revoked or rs.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad refresh")
    rs.revoked = True
    user = await session.get(User, rs.user_id)
    await session.flush()
    return await _issue_pair(session, user)


@router.post("/logout", status_code=204)
async def logout(data: RefreshIn, session: Annotated[AsyncSession, Depends(get_session)]):
    rs = await session.get(RefreshSession, data.refresh_token)
    if rs:
        rs.revoked = True
        await session.commit()


@router.post("/introspect", response_model=IntrospectOut)
async def introspect(data: IntrospectIn, session: Annotated[AsyncSession, Depends(get_session)]):
    try:
        payload = decode_token(data.token)
    except jwt.PyJWTError:
        return IntrospectOut(active=False)
    user = await session.get(User, payload.get("sub"))
    if not user:
        return IntrospectOut(active=False)
    return IntrospectOut(active=True, user_id=user.id, email=user.email)
