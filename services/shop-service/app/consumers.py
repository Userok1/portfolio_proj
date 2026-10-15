"""Consumer payment.* -> смена статуса заказа + списание/возврат резерва."""
import json
import logging

import aio_pika
from sqlalchemy import select

from .core.config import settings
from .db.models import Order, OrderItem, ProcessedEvent, Stock
from .db.session import SessionLocal

log = logging.getLogger(__name__)
EXCHANGE = "vibemarket.events"
QUEUE = "shop.payment-result"


async def _handle_payment_event(payload: dict) -> None:
    etype = payload.get("type")
    event_id = str(payload.get("event_id", ""))
    order_id = payload.get("order_id")
    async with SessionLocal() as s:
        if event_id and await s.get(ProcessedEvent, event_id):
            return  # уже обработано
        order = await s.get(Order, order_id)
        if not order or order.status != "pending_payment":
            return
        items = (await s.execute(select(OrderItem).where(OrderItem.order_id == order.id))).scalars().all()
        if etype == "payment.succeeded":
            order.status = "paid"
            for it in items:
                st = await s.get(Stock, it.product_id)
                if st:
                    st.qty -= it.qty
                    st.reserved -= it.qty
        else:  # payment.failed
            order.status = "cancelled"
            for it in items:
                st = await s.get(Stock, it.product_id)
                if st:
                    st.reserved -= it.qty
        if event_id:
            s.add(ProcessedEvent(event_id=event_id))
        await s.commit()


async def run_consumer() -> None:
    try:
        conn = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    except Exception as e:  # noqa: BLE001
        log.warning("shop consumer disabled (no rabbit): %s", e)
        return
    async with conn:
        ch = await conn.channel()
        await ch.set_qos(prefetch_count=10)
        ex = await ch.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
        dlx = await ch.declare_exchange("vibemarket.dlx", aio_pika.ExchangeType.TOPIC, durable=True)
        q = await ch.declare_queue(QUEUE, durable=True, arguments={"x-dead-letter-exchange": "vibemarket.dlx"})
        await q.bind(ex, "payment.*")

        async with q.iterator() as it:
            async for msg in it:
                async with msg.process(requeue=False):
                    try:
                        await _handle_payment_event(json.loads(msg.body.decode()))
                    except Exception as e:  # noqa: BLE001
                        log.exception("payment event failed: %s", e)
