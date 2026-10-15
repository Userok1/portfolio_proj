from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class OrderCreateIn(BaseModel):
    address: str
    delivery_method: str = "pickup"  # pickup | courier


class OrderItemOut(BaseModel):
    product_id: UUID
    title_snapshot: str
    price_snapshot: Decimal
    qty: int


class OrderOut(BaseModel):
    id: UUID
    status: str
    total: Decimal
    address: str
    delivery_method: str
    items: list[OrderItemOut] = []
