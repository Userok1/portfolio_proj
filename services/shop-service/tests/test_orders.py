from decimal import Decimal
from uuid import uuid4

from app.api.routes_orders import _to_out
from app.db.models import Order, OrderItem


def test_to_out():
    oid = uuid4()
    o = Order(id=oid, user_id=uuid4(), status="pending_payment", total=Decimal("100.00"), address="SPb", delivery_method="pickup")
    items = [OrderItem(id=uuid4(), order_id=oid, product_id=uuid4(), title_snapshot="T", price_snapshot=Decimal("100.00"), qty=1)]
    out = _to_out(o, items)
    assert out.id == oid
    assert out.total == Decimal("100.00")
    assert len(out.items) == 1
