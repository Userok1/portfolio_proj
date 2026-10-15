from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .deps import get_session, get_user_id
from ..db.models import Payment
from ..flow import mark_and_publish
from ..providers.base import ProviderError
from ..providers.factory import get_provider
from ..schemas.payments import PaymentOut

router = APIRouter(prefix="/payments", tags=["payments"])


def _out(p: Payment) -> PaymentOut:
    return PaymentOut(id=p.id, order_id=p.order_id, amount=p.amount, status=p.status, pay_url=p.pay_url, provider_payment_id=p.provider_payment_id)


@router.get("/by-session/{sid}", response_model=PaymentOut)
async def get_by_session(sid: str, user_id: UUID = Depends(get_user_id), session: AsyncSession = Depends(get_session)):
    """Нужен success-странице: Stripe возвращает только session_id, order_id узнаем здесь."""
    p = (await session.execute(select(Payment).where(Payment.provider_payment_id == sid))).scalar_one_or_none()
    if not p or p.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return _out(p)


@router.get("/{pid}", response_model=PaymentOut)
async def get_payment(pid: UUID, user_id: UUID = Depends(get_user_id), session: AsyncSession = Depends(get_session)):
    p = await session.get(Payment, pid)
    if not p or p.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return _out(p)


@router.get("/by-order/{oid}", response_model=PaymentOut)
async def get_by_order(oid: UUID, user_id: UUID = Depends(get_user_id), session: AsyncSession = Depends(get_session)):
    p = (await session.execute(select(Payment).where(Payment.order_id == oid))).scalar_one_or_none()
    if not p or p.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return _out(p)


@router.post("/by-order/{oid}/sync", response_model=PaymentOut)
async def sync_status(oid: UUID, user_id: UUID = Depends(get_user_id), session: AsyncSession = Depends(get_session)):
    """Перепроверить статус в Stripe (после success_url). Если сессии еще нет — создает."""
    p = (await session.execute(select(Payment).where(Payment.order_id == oid))).scalar_one_or_none()
    if not p or p.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    provider = get_provider()
    if provider is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "provider disabled (no keys)")
    try:
        if not p.provider_payment_id:
            intent = await provider.create_intent(p.order_id, p.amount)
            p.provider_payment_id = intent.provider_payment_id
            p.pay_url = intent.pay_url
            await session.commit()
            return _out(p)
        verified = await provider.get_status(p.provider_payment_id)
    except ProviderError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)[:300])
    await mark_and_publish(p, verified, session)
    return _out(p)


@router.post("/by-order/{oid}/cancel", response_model=PaymentOut)
async def cancel_payment(oid: UUID, user_id: UUID = Depends(get_user_id), session: AsyncSession = Depends(get_session)):
    p = (await session.execute(select(Payment).where(Payment.order_id == oid))).scalar_one_or_none()
    if not p or p.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    if p.status in ("succeeded", "canceled"):
        return _out(p)
    provider = get_provider()
    if provider is not None and p.provider_payment_id:
        try:
            verified = await provider.cancel(p.provider_payment_id)
        except ProviderError as e:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)[:300])
        await mark_and_publish(p, verified, session)
    else:
        await mark_and_publish(p, "canceled", session)
    return _out(p)
