"""httpx-клиенты к трем API. Все вызовы серверные (BFF), follow_redirects из-за 307 на /orders и /cart."""
import uuid

import httpx

from .config import settings


class BackendError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"{status}: {detail}")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=10.0, follow_redirects=True)


def _auth(access: str) -> dict:
    return {"Authorization": f"Bearer {access}"}


def _raise(r: httpx.Response) -> None:
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text[:200])
        except Exception:
            detail = r.text[:200]
        raise BackendError(r.status_code, str(detail))


async def auth_register(email: str, password: str) -> dict:
    async with _client() as c:
        r = await c.post(f"{settings.AUTH_API_URL}/auth/register", json={"email": email, "password": password})
    _raise(r)
    return r.json()


async def auth_login(email: str, password: str) -> dict:
    async with _client() as c:
        r = await c.post(f"{settings.AUTH_API_URL}/auth/login", json={"email": email, "password": password})
    _raise(r)
    return r.json()


async def shop_list() -> list:
    async with _client() as c:
        r = await c.get(f"{settings.SHOP_API_URL}/products")
    _raise(r)
    return r.json()


async def shop_get(pid: str) -> dict:
    async with _client() as c:
        r = await c.get(f"{settings.SHOP_API_URL}/products/{pid}")
    _raise(r)
    return r.json()


async def shop_create(access: str, data: dict) -> dict:
    async with _client() as c:
        r = await c.post(f"{settings.SHOP_API_URL}/products", json=data, headers=_auth(access))
    _raise(r)
    return r.json()


async def cart_list(access: str) -> list:
    async with _client() as c:
        r = await c.get(f"{settings.SHOP_API_URL}/cart/", headers=_auth(access))
    _raise(r)
    return r.json()


async def cart_add(access: str, pid: str, qty: int) -> list:
    async with _client() as c:
        r = await c.post(f"{settings.SHOP_API_URL}/cart/items", json={"product_id": pid, "qty": qty}, headers=_auth(access))
    _raise(r)
    return r.json()


async def cart_del(access: str, pid: str) -> list:
    async with _client() as c:
        r = await c.request("DELETE", f"{settings.SHOP_API_URL}/cart/items/{pid}", headers=_auth(access))
    _raise(r)
    return r.json()


async def order_create(access: str, address: str, delivery: str) -> dict:
    async with _client() as c:
        r = await c.post(
            f"{settings.SHOP_API_URL}/orders/",
            json={"address": address, "delivery_method": delivery},
            headers={**_auth(access), "Idempotency-Key": uuid.uuid4().hex},
        )
    _raise(r)
    return r.json()


async def order_my(access: str) -> list:
    async with _client() as c:
        r = await c.get(f"{settings.SHOP_API_URL}/orders/my", headers=_auth(access))
    _raise(r)
    return r.json()


async def order_get(access: str, oid: str) -> dict:
    async with _client() as c:
        r = await c.get(f"{settings.SHOP_API_URL}/orders/{oid}", headers=_auth(access))
    _raise(r)
    return r.json()


async def pay_by_order(access: str, oid: str) -> dict | None:
    async with _client() as c:
        r = await c.get(f"{settings.PAY_API_URL}/payments/by-order/{oid}", headers=_auth(access))
    if r.status_code == 404:
        return None
    _raise(r)
    return r.json()


async def pay_by_session(access: str, sid: str) -> dict | None:
    async with _client() as c:
        r = await c.get(f"{settings.PAY_API_URL}/payments/by-session/{sid}", headers=_auth(access))
    if r.status_code == 404:
        return None
    _raise(r)
    return r.json()


async def pay_sync(access: str, oid: str) -> dict:
    async with _client() as c:
        r = await c.post(f"{settings.PAY_API_URL}/payments/by-order/{oid}/sync", headers=_auth(access))
    _raise(r)
    return r.json()


async def pay_cancel(access: str, oid: str) -> dict:
    async with _client() as c:
        r = await c.post(f"{settings.PAY_API_URL}/payments/by-order/{oid}/cancel", headers=_auth(access))
    _raise(r)
    return r.json()
