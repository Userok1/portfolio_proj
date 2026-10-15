from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PaymentOut(BaseModel):
    id: UUID
    order_id: UUID
    amount: Decimal
    status: str
    pay_url: str | None = None
    provider_payment_id: str | None = None


class WebhookIn(BaseModel):
    """Заглушка: принимаем любой JSON от будущего провайдера, только логируем."""
    model_config = {"extra": "allow"}
