from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .deps import get_session
from ..db.models import Payment, WebhookLog
from ..flow import mark_and_publish
from ..providers.base import ProviderError
from ..providers.factory import get_provider
from ..providers.stripe import to_minor

router = APIRouter(tags=["webhooks"])

# Stripe event -> наш внутренний статус
SUCCEEDED = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
CANCELED = {"checkout.session.expired", "checkout.session.async_payment_failed"}


# @router.post("/webhooks/payment-provider")
# async def provider_webhook_legacy(request: Request, session: AsyncSession = Depends(get_session)):
#     """Legacy-заглушка, оставлена для совместимости. Только логирует."""
#     raw = (await request.body()).decode() or "{}"
#     session.add(WebhookLog(payload=raw[:8000]))
#     await session.commit()
#     return {"received": True}


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    sig: str = Header(default="", alias="Stripe-Signature"),
):
    """Вебхук Stripe. Подпись проверяем обязательно (endpoint secret),
    событие ищем по session id с fallback на metadata.order_id."""
    raw = await request.body()
    session.add(WebhookLog(payload=raw.decode()[:8000] or "{}"))
    await session.commit()

    provider = get_provider()
    if provider is None:
        return {"received": False, "error": "provider disabled"}
    try:
        event = provider.verify_webhook(raw, sig)
    except ProviderError as e:
        return {"received": False, "error": str(e)[:200]}

    etype = event.get("type", "")
    obj = event.get("data", {}).get("object", {}) or {}
    session_id = obj.get("id")
    if not session_id:
        return {"received": False, "error": "no session id"}

    payment = (await session.execute(select(Payment).where(Payment.provider_payment_id == session_id))).scalar_one_or_none()
    if payment is None:
        meta = obj.get("metadata") or {}
        ref = meta.get("order_id") or obj.get("client_reference_id")
        if ref:
            payment = (await session.execute(select(Payment).where(Payment.order_id == ref))).scalar_one_or_none()
            if payment and not payment.provider_payment_id:
                payment.provider_payment_id = session_id
                await session.commit()
    if payment is None:
        return {"received": True, "matched": False}

    # сверка суммы (Stripe — в копейках)
    total = obj.get("amount_total")
    if total is not None and total != to_minor(payment.amount):
        return {"received": True, "matched": True, "error": "amount mismatch"}

    if etype in SUCCEEDED:
        routing = await mark_and_publish(payment, "succeeded", session)
    elif etype in CANCELED:
        routing = await mark_and_publish(payment, "canceled", session)
    else:
        return {"received": True, "matched": True, "ignored": etype}
    return {"received": True, "matched": True, "status": payment.status, "published": routing}
