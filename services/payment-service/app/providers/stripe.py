"""Клиент Stripe (Checkout Sessions, hosted page).

Docs: https://docs.stripe.com/api/checkout/sessions
- Создание: POST /v1/checkout/sessions (form-encoded, Basic Auth secret key,
  заголовок Idempotence-Key). Ответ: id (cs_...), url (редирект), payment_status.
- Суммы — в минимальных единицах (копейки): 100.00 RUB -> 10000.
- Привязка заказа: client_reference_id + metadata[order_id].
- Вебхуки: checkout.session.completed -> succeeded;
  checkout.session.expired / checkout.session.async_payment_failed -> canceled.
  Подпись: заголовок Stripe-Signature "t=...,v1=...", HMAC-SHA256("t.raw", endpoint_secret).
"""
import hashlib
import hmac
import json
import time
import uuid
from decimal import Decimal
from urllib.parse import parse_qsl
from uuid import UUID

import httpx

from .base import ProviderError, ProviderIntent

DEFAULT_API_URL = "https://api.stripe.com"


def to_minor(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())


def normalize_session(data: dict) -> str:
    """payment_status paid -> succeeded; status expired -> canceled; иначе pending."""
    if data.get("payment_status") == "paid":
        return "succeeded"
    if data.get("status") == "expired":
        return "canceled"
    return "pending"


class StripeProvider:
    def __init__(
        self,
        secret_key: str,
        success_url: str,
        cancel_url: str,
        webhook_secret: str = "",
        currency: str = "rub",
        api_url: str = DEFAULT_API_URL,
        client: httpx.AsyncClient | None = None,
    ):
        if not secret_key:
            raise ProviderError("STRIPE_SECRET_KEY required")
        self._key = secret_key
        self._whsec = webhook_secret
        self._success_url = success_url
        self._cancel_url = cancel_url
        self._currency = currency.lower()
        self._api = api_url.rstrip("/")
        self._client = client

    def _headers(self, idem_key: str) -> dict:
        return {"Idempotence-Key": idem_key}

    async def _post(self, path: str, data: dict, idem: str) -> dict:
        if self._client is not None:
            resp = await self._client.post(f"{self._api}{path}", data=data, headers=self._headers(idem), auth=(self._key, ""))
        else:
            async with httpx.AsyncClient(base_url=self._api, auth=(self._key, ""), timeout=10.0) as client:
                resp = await client.post(path, data=data, headers=self._headers(idem))
        if resp.status_code not in (200, 201, 202):
            raise ProviderError(f"stripe {path} failed {resp.status_code}: {resp.text[:500]}")
        return resp.json()

    async def _get(self, path: str) -> dict:
        if self._client is not None:
            resp = await self._client.get(f"{self._api}{path}", auth=(self._key, ""))
        else:
            async with httpx.AsyncClient(base_url=self._api, auth=(self._key, ""), timeout=10.0) as client:
                resp = await client.get(path)
        if resp.status_code != 200:
            raise ProviderError(f"stripe {path} failed {resp.status_code}: {resp.text[:500]}")
        return resp.json()

    async def create_intent(self, order_id: UUID, amount: Decimal, email: str = "") -> ProviderIntent:
        data = {
            "mode": "payment",
            "success_url": self._success_url,
            "cancel_url": self._cancel_url,
            "client_reference_id": str(order_id),
            "metadata[order_id]": str(order_id),
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": self._currency,
            "line_items[0][price_data][unit_amount]": str(to_minor(amount)),
            "line_items[0][price_data][product_data][name]": f"Order {order_id}",
        }
        try:
            body = await self._post("/v1/checkout/sessions", data, idem=f"order-{order_id}")
        except ProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"stripe create error: {e}")
        if not body.get("id") or not body.get("url"):
            raise ProviderError(f"stripe create: no id/url in response: {json.dumps(body)[:300]}")
        return ProviderIntent(provider_payment_id=body["id"], pay_url=body["url"], status=normalize_session(body))

    async def get_status(self, provider_payment_id: str) -> str:
        try:
            body = await self._get(f"/v1/checkout/sessions/{provider_payment_id}")
        except ProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"stripe get error: {e}")
        return normalize_session(body)

    async def cancel(self, provider_payment_id: str) -> str:
        try:
            body = await self._post(f"/v1/checkout/sessions/{provider_payment_id}/expire", {}, idem=uuid.uuid4().hex)
        except ProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"stripe expire error: {e}")
        # expire возвращает сессию со status=expired -> canceled
        if body.get("status") == "expired":
            return "canceled"
        return normalize_session(body)

    def verify_webhook(self, raw: bytes, sig_header: str, tolerance: int = 300) -> dict:
        """Проверяет подпись Stripe и возвращает событие. Бросает ProviderError."""
        if not self._whsec:
            raise ProviderError("STRIPE_WEBHOOK_SECRET required for verification")
        try:
            parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
            ts = int(parts["t"])
            v1s = [v for k, v in parse_qsl(sig_header.replace(",", "&")) if k == "v1"]
            if not v1s:
                raise KeyError("v1")
        except Exception:
            raise ProviderError("bad Stripe-Signature header")
        if abs(time.time() - ts) > tolerance:
            raise ProviderError("webhook timestamp outside tolerance")
        expected = hmac.new(self._whsec.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, v) for v in v1s):
            raise ProviderError("webhook signature mismatch")
        try:
            return json.loads(raw.decode())
        except Exception:
            raise ProviderError("webhook bad json")
