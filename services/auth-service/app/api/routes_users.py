from typing import Annotated

from fastapi import APIRouter, Depends

from ..api.deps import get_current_user
from ..db.models import User
from ..schemas.auth import MeOut

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=MeOut)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return MeOut(id=user.id, email=user.email)
