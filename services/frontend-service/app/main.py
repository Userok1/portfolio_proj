from decimal import Decimal
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .core import api
from .core.api import BackendError
from .core.sessions import COOKIE, create, drop, get

app = FastAPI(title="frontend-service")
app.mount("/static", StaticFiles(directory="app/static"))
tpl = Jinja2Templates(directory="app/templates")


def ctx(request: Request, **kw):
    s = get(request.cookies.get(COOKIE))
    base = {"request": request, "email": s.email if s else None}
    base.update(kw)
    return base


def safe_next(nxt: str) -> str:
    """Только внутренние пути — защита от open redirect."""
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return "/"


def need(request: Request):
    s = get(request.cookies.get(COOKIE))
    if not s:
        back = str(request.url.path)
        if request.url.query:
            back += "?" + request.url.query
        return None, RedirectResponse(f"/login?next={quote(back, safe='')}", status_code=303)
    return s, None


def redir(url: str, err: str = "") -> RedirectResponse:
    return RedirectResponse(f"{url}?err={err}" if err else url, status_code=303)


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
async def catalog(request: Request, err: str = ""):
    try:
        products = await api.shop_list()
    except BackendError as e:
        return tpl.TemplateResponse("catalog.html", ctx(request, products=[], err=f"Каталог недоступен: {e.detail}"))
    return tpl.TemplateResponse("catalog.html", ctx(request, products=products, err=err))


@app.get("/products/{pid}", response_class=HTMLResponse)
async def product(request: Request, pid: str):
    try:
        p = await api.shop_get(pid)
    except BackendError:
        return redir("/", "Товар не найден")
    return tpl.TemplateResponse("product.html", ctx(request, p=p))


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, err: str = "", next: str = ""):
    return tpl.TemplateResponse("login.html", ctx(request, err=err, next=next))


@app.post("/login")
async def login(request: Request, email: str = Form(), password: str = Form(), next: str = Form("")):
    try:
        t = await api.auth_login(email, password)
    except BackendError:
        return redir(f"/login?next={quote(next, safe='')}" if next else "/login", "Неверный email или пароль")
    r = RedirectResponse(safe_next(next), status_code=303)
    r.set_cookie(COOKIE, create(t["access_token"], t["refresh_token"], email), httponly=True)
    return r


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, err: str = "", next: str = ""):
    return tpl.TemplateResponse("register.html", ctx(request, err=err, next=next))


@app.post("/register")
async def register(request: Request, email: str = Form(), password: str = Form(), next: str = Form("")):
    try:
        t = await api.auth_register(email, password)
    except BackendError as e:
        return redir(f"/register?next={quote(next, safe='')}" if next else "/register", e.detail if e.status == 409 else "Ошибка регистрации")
    r = RedirectResponse(safe_next(next), status_code=303)
    r.set_cookie(COOKIE, create(t["access_token"], t["refresh_token"], email), httponly=True)
    return r


@app.post("/logout")
async def logout(request: Request):
    drop(request.cookies.get(COOKIE))
    r = RedirectResponse("/", status_code=303)
    r.delete_cookie(COOKIE)
    return r


@app.get("/cart", response_class=HTMLResponse)
async def cart(request: Request, err: str = ""):
    s, red = need(request)
    if red:
        return red
    try:
        items_raw = await api.cart_list(s.access)
        prods = {p["id"]: p for p in await api.shop_list()}
        items, total = [], Decimal("0")
        for i in items_raw:
            p = prods.get(i["product_id"], {"title": i["product_id"], "price": "0"})
            ssum = Decimal(str(p["price"])) * i["qty"]
            total += ssum
            items.append({**i, "title": p["title"], "sum": ssum})
    except BackendError as e:
        return tpl.TemplateResponse("cart.html", ctx(request, items=[], total=0, err=e.detail))
    return tpl.TemplateResponse("cart.html", ctx(request, items=items, total=total, err=err))


@app.post("/cart/add")
async def cart_add(request: Request, pid: str = Form(), qty: int = Form(1)):
    s, red = need(request)
    if red:
        return red
    try:
        await api.cart_add(s.access, pid, max(qty, 1))
    except BackendError as e:
        return redir("/cart", e.detail)
    return RedirectResponse("/cart", status_code=303)


@app.post("/cart/remove/{pid}")
async def cart_remove(request: Request, pid: str):
    s, red = need(request)
    if red:
        return red
    try:
        await api.cart_del(s.access, pid)
    except BackendError:
        pass
    return RedirectResponse("/cart", status_code=303)


@app.get("/checkout", response_class=HTMLResponse)
async def checkout_page(request: Request, err: str = ""):
    s, red = need(request)
    if red:
        return red
    return tpl.TemplateResponse("checkout.html", ctx(request, err=err))


@app.post("/checkout")
async def checkout(request: Request, address: str = Form(), delivery: str = Form("pickup")):
    s, red = need(request)
    if red:
        return red
    try:
        o = await api.order_create(s.access, address, delivery)
    except BackendError as e:
        return redir("/checkout", e.detail)
    return RedirectResponse(f"/orders/{o['id']}", status_code=303)


@app.get("/orders", response_class=HTMLResponse)
async def orders(request: Request, err: str = ""):
    s, red = need(request)
    if red:
        return red
    try:
        lst = await api.order_my(s.access)
    except BackendError as e:
        return tpl.TemplateResponse("orders.html", ctx(request, orders=[], err=e.detail))
    return tpl.TemplateResponse("orders.html", ctx(request, orders=lst, err=err))


@app.get("/orders/{oid}", response_class=HTMLResponse)
async def order_detail(request: Request, oid: str, paid: int = 0):
    s, red = need(request)
    if red:
        return red
    try:
        o = await api.order_get(s.access, oid)
        pay = await api.pay_by_order(s.access, oid)
    except BackendError:
        return redir("/orders", "Заказ не найден")
    return tpl.TemplateResponse("order_detail.html", ctx(request, o=o, pay=pay, paid=paid))


@app.get("/payment/success", response_class=HTMLResponse)
async def payment_success(request: Request, session_id: str = ""):
    """Сюда Stripe возвращает покупателя (success_url). Находим заказ по сессии,
    подтягиваем статус и ведем на страницу заказа с флагом успеха."""
    s, red = need(request)
    if red:
        return red
    if not session_id:
        return redir("/orders", "Нет session_id")
    try:
        pay = await api.pay_by_session(s.access, session_id)
        if not pay:
            return redir("/orders", "Платеж не найден")
        await api.pay_sync(s.access, pay["order_id"])
    except BackendError as e:
        return redir("/orders", e.detail)
    return RedirectResponse(f"/orders/{pay['order_id']}?paid=1", status_code=303)


@app.post("/orders/{oid}/sync")
async def order_sync(request: Request, oid: str):
    s, red = need(request)
    if red:
        return red
    try:
        await api.pay_sync(s.access, oid)
    except BackendError as e:
        return redir(f"/orders/{oid}", e.detail)
    return RedirectResponse(f"/orders/{oid}", status_code=303)


@app.post("/orders/{oid}/cancel-pay")
async def order_cancel_pay(request: Request, oid: str):
    s, red = need(request)
    if red:
        return red
    try:
        await api.pay_cancel(s.access, oid)
    except BackendError as e:
        return redir(f"/orders/{oid}", e.detail)
    return RedirectResponse(f"/orders/{oid}", status_code=303)


@app.get("/admin/products", response_class=HTMLResponse)
async def admin_products(request: Request, err: str = ""):
    s, red = need(request)
    if red:
        return red
    try:
        products = await api.shop_list()
    except BackendError as e:
        return tpl.TemplateResponse("admin_products.html", ctx(request, products=[], err=e.detail))
    return tpl.TemplateResponse("admin_products.html", ctx(request, products=products, err=err))


@app.post("/admin/products")
async def admin_create(request: Request, sku: str = Form(), title: str = Form(), price: str = Form(), qty: int = Form(0)):
    s, red = need(request)
    if red:
        return red
    try:
        await api.shop_create(s.access, {"sku": sku, "title": title, "price": price, "qty": max(qty, 0)})
    except BackendError as e:
        return redir("/admin/products", e.detail)
    return RedirectResponse("/admin/products", status_code=303)
