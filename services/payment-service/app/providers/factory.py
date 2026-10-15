"""Фабрика провайдера: Stripe при наличии secret key, иначе None (dev-режим без эквайринга)."""
from .base import PaymentProvider
from .stripe import StripeProvider
from ..core.config import settings


def get_provider() -> PaymentProvider | None:
    if not settings.STRIPE_ENABLED:
        return None
    if not settings.STRIPE_SECRET_KEY:
        return None
    return StripeProvider(
        secret_key=settings.STRIPE_SECRET_KEY,
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
        webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
        currency=settings.STRIPE_CURRENCY,
        api_url=settings.STRIPE_API_URL,
    )
