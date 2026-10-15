"""Consumer order.created -> Payment(pending) + Checkout Session в Stripe."""
import json
import logging
from decimal import Decimal
from uuid import UUID

import aio_pika
from sqlalchemy import select

from .core.config import settings
from .db.models import Payment, ProcessedEvent
from .db.session import SessionLocal
from .providers.base import ProviderError
from .providers.factory import get_provider

log = logging.getLogger(__name__)
EXCHANGE = "vibemarket.events"
QUEUE = "pay.order-created"


async def create_payment_from_event(payload: dict) -> bool:
    """Вынесено для тестов. Возвращает True если создан."""
    event_id = str(payload.get("event_id", ""))
    order_id = UUID(payload["order_id"])
    user_id = UUID(payload["user_id"])
    amount = Decimal(str(payload["amount"]))
    async with SessionLocal() as s:
        if event_id and await s.get(ProcessedEvent, event_id):
            return False
        exists = (await s.execute(select(Payment).where(Payment.order_id == order_id))).scalar_one_or_none()
        if exists:
            return False
        payment = Payment(order_id=order_id, user_id=user_id, amount=amount, status="pending")
        s.add(payment)
        if event_id:
            s.add(ProcessedEvent(event_id=event_id))
        await s.commit()

    # сессия Stripe — идемпотентна по order_id (Idempotence-Key: order-{id})
    provider = get_provider()
    if provider is not None:
        try:
            intent = await provider.create_intent(order_id, amount)
            async with SessionLocal() as s2:
                p = (await s2.execute(select(Payment).where(Payment.order_id == order_id))).scalar_one_or_none()
                if p and not p.provider_payment_id:
                    p.provider_payment_id = intent.provider_payment_id
                    p.pay_url = intent.pay_url
                    await s2.commit()
        except ProviderError as e:
            log.warning("stripe create skipped for order %s: %s", order_id, e)
    return True


async def run_consumer() -> None:
    try:
        conn = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    except Exception as e:  # noqa: BLE001
        log.warning("pay consumer disabled (no rabbit): %s", e)
        return
    async with conn:
        ch = await conn.channel()
        await ch.set_qos(prefetch_count=10)
        ex = await ch.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
        q = await ch.declare_queue(QUEUE, durable=True, arguments={"x-dead-letter-exchange": "vibemarket.dlx"})
        await q.bind(ex, "order.created")
        async with q.iterator() as it:
            async for msg in it:
                async with msg.process(requeue=False):
                    try:
                        await create_payment_from_event(json.loads(msg.body.decode()))
                    except Exception as e:  # noqa: BLE001
                        log.exception("order.created failed: %s", e)
