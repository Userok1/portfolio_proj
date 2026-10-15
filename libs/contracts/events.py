from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    from datetime import timezone
    return datetime.now(timezone.utc)


class BaseEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=_utcnow)
    v: int = 1


class OrderCreatedV1(BaseEvent):
    type: Literal["order.created"] = "order.created"
    order_id: UUID
    user_id: UUID
    amount: str  # Decimal as string to avoid float issues


class PaymentSucceededV1(BaseEvent):
    type: Literal["payment.succeeded"] = "payment.succeeded"
    order_id: UUID
    payment_id: UUID


class PaymentFailedV1(BaseEvent):
    type: Literal["payment.failed"] = "payment.failed"
    order_id: UUID
    payment_id: UUID
    reason: str = "failed"


class UserRegisteredV1(BaseEvent):
    type: Literal["user.registered"] = "user.registered"
    user_id: UUID
    email: str


EXCHANGE = "vibemarket.events"
ROUTING = {
    "order.created": "order.created",
    "payment.succeeded": "payment.succeeded",
    "payment.failed": "payment.failed",
    "user.registered": "user.registered",
}
