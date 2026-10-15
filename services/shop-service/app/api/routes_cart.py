from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .deps import get_session, get_user_id
from ..db.models import CartItem
from ..schemas.cart import CartAddIn, CartItemOut

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("/", response_model=list[CartItemOut])
async def get_cart(user_id: UUID = Depends(get_user_id), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(CartItem).where(CartItem.user_id == user_id))).scalars().all()
    return [CartItemOut(product_id=r.product_id, qty=r.qty) for r in rows]


@router.post("/items", response_model=list[CartItemOut])
async def add_item(data: CartAddIn, user_id: UUID = Depends(get_user_id), session: AsyncSession = Depends(get_session)):
    item = await session.get(CartItem, (user_id, data.product_id))
    if item:
        item.qty += data.qty
    else:
        session.add(CartItem(user_id=user_id, product_id=data.product_id, qty=data.qty))
    await session.commit()
    rows = (await session.execute(select(CartItem).where(CartItem.user_id == user_id))).scalars().all()
    return [CartItemOut(product_id=r.product_id, qty=r.qty) for r in rows]


@router.delete("/items/{pid}", response_model=list[CartItemOut])
async def del_item(pid: UUID, user_id: UUID = Depends(get_user_id), session: AsyncSession = Depends(get_session)):
    item = await session.get(CartItem, (user_id, pid))
    if item:
        await session.delete(item)
        await session.commit()
    rows = (await session.execute(select(CartItem).where(CartItem.user_id == user_id))).scalars().all()
    return [CartItemOut(product_id=r.product_id, qty=r.qty) for r in rows]
