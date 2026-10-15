from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .deps import get_session, get_user_id
from ..db.models import Product, Stock
from ..schemas.catalog import ProductCreate, ProductOut

router = APIRouter(tags=["catalog"])


@router.get("/products", response_model=list[ProductOut])
async def list_products(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Product).where(Product.is_active == True).limit(100))).scalars().all()  # noqa: E712
    return [ProductOut(**{c: getattr(p, c) for c in ("id", "sku", "title", "description", "price", "is_active", "category_id")}) for p in rows]


@router.get("/products/{pid}", response_model=ProductOut)
async def get_product(pid: UUID, session: AsyncSession = Depends(get_session)):
    p = await session.get(Product, pid)
    if not p or not p.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return ProductOut(id=p.id, sku=p.sku, title=p.title, description=p.description, price=p.price, is_active=p.is_active, category_id=p.category_id)


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(
    data: ProductCreate,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_user_id),
):
    """Админская ручка. Упрощение MVP: любой залогиненный. Роли buyer/admin — Phase 2."""
    p = Product(sku=data.sku, title=data.title, description=data.description, price=data.price, category_id=data.category_id)
    session.add(p)
    await session.flush()
    session.add(Stock(product_id=p.id, qty=data.qty, reserved=0))
    await session.commit()
    return ProductOut(id=p.id, sku=p.sku, title=p.title, description=p.description, price=p.price, is_active=p.is_active, category_id=p.category_id)
