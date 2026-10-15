import hashlib
import hmac
import json
import time
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from app.flow import to_event
from app.providers.base import ProviderError
from app.providers.stripe import StripeProvider, normalize_session, to_minor


def _mock_client(routes: dict) -> httpx.AsyncClient:
    def handler(req: httpx.Request) -> httpx.Response:
        key = (req.method, req.url.path)
        if key in routes:
            status, body = routes[key]
            return httpx.Response(status, json=body)
        return httpx.Response(404, json={"error": "no mock"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.stripe.com")


def prov(client=None) -> StripeProvider:
    return StripeProvider(
        secret_key="sk_test_123",
        success_url="http://localhost/done?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://localhost/cancelled",
        webhook_secret="whsec_test",
        client=client,
    )


def test_minor_units():
    assert to_minor(Decimal("100.00")) == 10000
    assert to_minor(Decimal("99.99")) == 9999


def test_normalize():
    assert normalize_session({"payment_status": "paid"}) == "succeeded"
    assert normalize_session({"status": "expired"}) == "canceled"
    assert normalize_session({"payment_status": "unpaid", "status": "open"}) == "pending"


def test_to_event():
    assert to_event("succeeded") == "payment.succeeded"
    assert to_event("canceled") == "payment.failed"
    assert to_event("pending") is None


async def test_create_session_ok():
    sid = "cs_test_123"
    client = _mock_client(
        {("POST", "/v1/checkout/sessions"): (200, {"id": sid, "url": "https://checkout.stripe.com/c/pay/1", "payment_status": "unpaid", "status": "open"})}
    )
    intent = await prov(client).create_intent(uuid4(), Decimal("100.00"))
    assert intent.provider_payment_id == sid
    assert intent.pay_url.startswith("https://checkout.stripe.com/")


async def test_create_session_error():
    client = _mock_client({("POST", "/v1/checkout/sessions"): (401, {"error": {"message": "bad key"}})})
    with pytest.raises(ProviderError):
        await prov(client).create_intent(uuid4(), Decimal("10.00"))


async def test_get_and_cancel():
    sid = "cs_test_1"
    client = _mock_client(
        {
            ("GET", f"/v1/checkout/sessions/{sid}"): (200, {"id": sid, "payment_status": "paid"}),
            ("POST", f"/v1/checkout/sessions/{sid}/expire"): (200, {"id": sid, "status": "expired"}),
        }
    )
    p = prov(client)
    assert await p.get_status(sid) == "succeeded"
    assert await p.cancel(sid) == "canceled"


async def test_idempotence_key_sent():
    seen: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["idem"] = req.headers.get("Idempotence-Key")
        return httpx.Response(200, json={"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/1"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.stripe.com")
    await prov(client).create_intent(uuid4(), Decimal("5.00"))
    assert seen["idem"] and seen["idem"].startswith("order-")


def _sign(raw: bytes, secret: str = "whsec_test") -> str:
    ts = int(time.time())
    v1 = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return f"t={ts},v1={v1}"


def test_webhook_verify_ok():
    event = {"id": "evt_1", "type": "checkout.session.completed", "data": {"object": {"id": "cs_1"}}}
    raw = json.dumps(event).encode()
    out = prov().verify_webhook(raw, _sign(raw))
    assert out["type"] == "checkout.session.completed"


def test_webhook_tampered_payload():
    event = {"id": "evt_1", "type": "checkout.session.completed", "data": {"object": {"id": "cs_1"}}}
    raw = json.dumps(event).encode()
    sig = _sign(raw)
    bad = json.dumps({**event, "type": "checkout.session.expired"}).encode()
    with pytest.raises(ProviderError):
        prov().verify_webhook(bad, sig)


def test_webhook_stale_timestamp():
    raw = b'{"type":"x"}'
    old = int(time.time()) - 1000
    v1 = hmac.new(b"whsec_test", f"{old}.".encode() + raw, hashlib.sha256).hexdigest()
    with pytest.raises(ProviderError):
        prov().verify_webhook(raw, f"t={old},v1={v1}")
