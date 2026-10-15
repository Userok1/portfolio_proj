import json
import uuid
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .deps import get_idempotency_key, get_session, get_user_id
from ..core.rabbit import publish_event
from ..db.models import CartItem, Order, OrderItem, Product, Stock
from ..schemas.orders import OrderCreateIn, OrderItemOut, OrderOut

router = APIRouter(prefix="/orders", tags=["orders"])


def _to_out(order: Order, items: list[OrderItem]) -> OrderOut:
    return OrderOut(
        id=order.id,
        status=order.status,
        total=order.total,
        address=order.address,
        delivery_method=order.delivery_method,
        items=[OrderItemOut(product_id=i.product_id, title_snapshot=i.title_snapshot, price_snapshot=i.price_snapshot, qty=i.qty) for i in items],
    )


@router.post("/", response_model=OrderOut, status_code=201)
async def create_order(
    data: OrderCreateIn,
    user_id: UUID = Depends(get_user_id),
    idempotency_key: str | None = Depends(get_idempotency_key),
    session: AsyncSession = Depends(get_session),
):
    if data.delivery_method not in ("pickup", "courier"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "bad delivery_method")

    # идемпотентность
    if idempotency_key:
        dup = (await session.execute(select(Order).where(Order.idempotency_key == idempotency_key))).scalar_one_or_none()
        if dup:
            items = (await session.execute(select(OrderItem).where(OrderItem.order_id == dup.id))).scalars().all()
            return _to_out(dup, list(items))

    cart = (await session.execute(select(CartItem).where(CartItem.user_id == user_id))).scalars().all()
    if not cart:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "cart empty")

    total = 0
    order = Order(user_id=user_id, status="pending_payment", total=0, address=data.address, delivery_method=data.delivery_method, idempotency_key=idempotency_key)
    session.add(order)
    await session.flush()

    for cart_item in cart:
        prod = await session.get(Product, cart_item.product_id)
        if not prod or not prod.is_active:
            raise HTTPException(status.HTTP_409_CONFLICT, f"product {cart_item.product_id} unavailable")
        # резерв остатка под блокировкой
        stock = (await session.execute(select(Stock).where(Stock.product_id == cart_item.product_id).with_for_update())).scalar_one_or_none()
        if not stock or stock.qty - stock.reserved < cart_item.qty:
            raise HTTPException(status.HTTP_409_CONFLICT, f"not enough stock for {prod.sku}")
        stock.reserved += cart_item.qty
        total += prod.price * cart_item.qty
        session.add(OrderItem(order_id=order.id, product_id=prod.id, title_snapshot=prod.title, price_snapshot=prod.price, qty=cart_item.qty))

    order.total = total
    await session.execute(delete(CartItem).where(CartItem.user_id == user_id))
    await session.commit()

    await publish_event(
        "order.created",
        json.dumps({"type": "order.created", "event_id": uuid.uuid4().hex, "order_id": str(order.id), "user_id": str(user_id), "amount": str(total)}).encode(),
    )
    items = (await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))).scalars().all()
    return _to_out(order, list(items))


@router.get("/my", response_model=list[OrderOut])
async def my_orders(user_id: UUID = Depends(get_user_id), session: AsyncSession = Depends(get_session)):
    orders = (await session.execute(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(50))).scalars().all()
    out = []
    for o in orders:
        items = (await session.execute(select(OrderItem).where(OrderItem.order_id == o.id))).scalars().all()
        out.append(_to_out(o, list(items)))
    return out


@router.get("/{oid}", response_model=OrderOut)
async def get_order(oid: UUID, user_id: UUID = Depends(get_user_id), session: AsyncSession = Depends(get_session)):
    o = await session.get(Order, oid)
    if not o or o.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    items = (await session.execute(select(OrderItem).where(OrderItem.order_id == o.id))).scalars().all()
    return _to_out(o, list(items))
