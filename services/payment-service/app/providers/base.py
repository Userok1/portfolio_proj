"""Интерфейс внешнего эквайринга. Реализация: stripe.py."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID


@dataclass
class ProviderIntent:
    provider_payment_id: str
    pay_url: str | None = None
    status: str = "pending"


class ProviderError(RuntimeError):
    pass


class PaymentProvider(Protocol):
    async def create_intent(self, order_id: UUID, amount: Decimal, email: str = "") -> ProviderIntent:
        ...

    async def get_status(self, provider_payment_id: str) -> str:
        """Возвращает нормализованный статус: pending | succeeded | canceled."""
        ...

    async def cancel(self, provider_payment_id: str) -> str:
        ...
