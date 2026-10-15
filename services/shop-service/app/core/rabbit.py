import logging

import aio_pika

from .config import settings

log = logging.getLogger(__name__)
EXCHANGE_NAME = "vibemarket.events"


async def publish_event(routing_key: str, body: bytes) -> None:
    try:
        conn = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        async with conn:
            ch = await conn.channel()
            ex = await ch.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
            await ex.publish(aio_pika.Message(body=body, delivery_mode=2), routing_key=routing_key)
    except Exception as e:
        log.warning("rabbit publish skipped (%s): %s", routing_key, e)
