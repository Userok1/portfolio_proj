"""Общая логика смены статуса Payment + публикация событий для shop-service."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from .core.rabbit import publish_event
from .db.models import Payment

TERMINAL = {"succeeded", "canceled"}


def to_event(status: str) -> str | None:
    if status == "succeeded":
        return "payment.succeeded"
    if status == "canceled":
        return "payment.failed"
    return None


async def mark_and_publish(payment: Payment, new_status: str, session: AsyncSession) -> str | None:
    """Обновляет статус (идемпотентно) и публикует событие. Возвращает routing_key или None."""
    if payment.status in TERMINAL:
        return None
    if payment.status == new_status:
        return None
    payment.status = new_status
    await session.commit()
    routing = to_event(new_status)
    if routing:
        import json

        await publish_event(
            routing,
            json.dumps(
                {
                    "type": routing,
                    "event_id": uuid.uuid4().hex,
                    "order_id": str(payment.order_id),
                    "payment_id": str(payment.id),
                }
            ).encode(),
        )
    return routing
