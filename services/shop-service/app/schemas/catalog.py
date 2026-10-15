from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class CategoryOut(BaseModel):
    id: UUID
    slug: str
    title: str


class ProductOut(BaseModel):
    id: UUID
    sku: str
    title: str
    description: str
    price: Decimal
    is_active: bool
    category_id: UUID | None = None


class ProductCreate(BaseModel):
    sku: str
    title: str
    description: str = ""
    price: Decimal
    category_id: UUID | None = None
    qty: int = 0
