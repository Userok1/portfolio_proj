from uuid import UUID

from pydantic import BaseModel


class CartAddIn(BaseModel):
    product_id: UUID
    qty: int = 1


class CartItemOut(BaseModel):
    product_id: UUID
    qty: int
