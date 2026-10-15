import pytest
from fastapi.testclient import TestClient

from app.core import sessions
from app.main import app

client = TestClient(app, follow_redirects=False)


def test_sessions_memory():
    sid = sessions.create("a", "r", "u@ex.ru")
    assert sessions.get(sid).email == "u@ex.ru"
    assert sessions.get("nope") is None
    sessions.drop(sid)
    assert sessions.get(sid) is None


def test_catalog(monkeypatch):
    async def fake_list():
        return [{"id": "1", "sku": "S", "title": "T", "price": "10.00"}]

    monkeypatch.setattr("app.main.api.shop_list", fake_list)
    r = client.get("/")
    assert r.status_code == 200
    assert "T" in r.text


def test_cart_requires_login():
    r = client.get("/cart")
    assert r.status_code == 303
    assert r.headers["location"] == "/login?next=%2Fcart"


def test_deep_link_keeps_query():
    r = client.get("/payment/success?session_id=cs_1")
    assert r.status_code == 303
    assert r.headers["location"] == "/login?next=%2Fpayment%2Fsuccess%3Fsession_id%3Dcs_1"


def test_login_honors_next(monkeypatch):
    async def fake_login(email, password):
        return {"access_token": "a", "refresh_token": "r"}

    monkeypatch.setattr("app.main.api.auth_login", fake_login)
    r = client.post("/login", data={"email": "u@ex.ru", "password": "p", "next": "/orders"})
    assert r.status_code == 303
    assert r.headers["location"] == "/orders"


def test_login_rejects_open_redirect(monkeypatch):
    async def fake_login(email, password):
        return {"access_token": "a", "refresh_token": "r"}

    monkeypatch.setattr("app.main.api.auth_login", fake_login)
    r = client.post("/login", data={"email": "u@ex.ru", "password": "p", "next": "https://evil.ex/"})
    assert r.headers["location"] == "/"
    r = client.post("/login", data={"email": "u@ex.ru", "password": "p", "next": "//evil.ex/"})
    assert r.headers["location"] == "/"


def test_login_sets_cookie(monkeypatch):
    async def fake_login(email, password):
        return {"access_token": "a", "refresh_token": "r"}

    monkeypatch.setattr("app.main.api.auth_login", fake_login)
    r = client.post("/login", data={"email": "u@ex.ru", "password": "p"})
    assert r.status_code == 303
    assert "vbm_sid" in r.headers.get("set-cookie", "")


def test_payment_success_redirect(monkeypatch):
    sid = sessions.create("a", "r", "u@ex.ru")

    async def fake_by_session(access, sid_):
        assert sid_ == "cs_test_1"
        return {"order_id": "o1"}

    async def fake_sync(access, oid):
        assert oid == "o1"
        return {}

    monkeypatch.setattr("app.main.api.pay_by_session", fake_by_session)
    monkeypatch.setattr("app.main.api.pay_sync", fake_sync)
    r = client.get("/payment/success?session_id=cs_test_1", cookies={"vbm_sid": sid})
    assert r.status_code == 303
    assert r.headers["location"] == "/orders/o1?paid=1"


def test_payment_success_no_session():
    r = client.get("/payment/success")
    assert r.status_code == 303  # редирект: /login (без сессии) или /orders (без sid)


def test_login_bad_creds(monkeypatch):
    from app.core.api import BackendError

    async def boom(email, password):
        raise BackendError(401, "bad")

    monkeypatch.setattr("app.main.api.auth_login", boom)
    r = client.post("/login", data={"email": "u@ex.ru", "password": "p"})
    assert r.status_code == 303
    assert "/login" in r.headers["location"]
