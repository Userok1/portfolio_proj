from app.providers.base import PaymentProvider
from app.providers.stripe import StripeProvider


def _prov() -> StripeProvider:
    return StripeProvider(secret_key="sk_test_x", success_url="http://l/done", cancel_url="http://l/cancel")


def test_provider_interface():
    assert hasattr(PaymentProvider, "create_intent")
    assert hasattr(PaymentProvider, "get_status")
    assert hasattr(PaymentProvider, "cancel")
    p = _prov()
    assert hasattr(p, "create_intent") and hasattr(p, "verify_webhook")
