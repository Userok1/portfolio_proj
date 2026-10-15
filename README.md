# VibeMarket — e-commerce микроcервисы (портфолио)

Физтовары. 4 сервиса, общение только через RabbitMQ. Эквайринг — Stripe.

## Сервисы
- `auth-service :8001` — register/login/refresh/logout, `GET /users/me`, `POST /auth/introspect`
- `shop-service :8002` — `GET /products`, `POST /cart/items`, `POST /orders` (резерв стока + `order.created`), `GET /orders/my`. Создание товара требует авторизации.
- `payment-service :8003` — `GET /payments/{id}`, `GET /payments/by-order/{oid}` (там `pay_url`), `POST /payments/by-order/{oid}/sync|cancel`, `POST /webhooks/stripe`
- `frontend-service :8004` — BFF на Jinja2: витрина, корзина, заказы, оплата, админка товаров. Сессии серверные (в памяти), JWT в браузер не уходят. Админка MVP: любой залогиненный (ролей нет — Phase 2).
- ⚠️ Открывай UI всегда через **один хост** (`localhost:8004`, не `127.0.0.1:8004`): cookie сессии привязана к хосту, а Stripe возвращает на `localhost` — иначе после оплаты попадешь на `/login` (сессия при этом жива; редирект сохраняет `?next=`, после входа вернешься куда шел).

Auth проверяется через `POST auth:8000/auth/introspect` по `httpx` (без shared JWT-валидации).

## Saga заказа
1. `POST /orders {address, delivery_method}` -> `pending_payment`, `stock.reserved+=qty`, publish `order.created`
2. payment consumer -> `Payment(pending)` + Checkout Session в Stripe (`POST /v1/checkout/sessions`, `pay_url` в `GET /payments/by-order/{oid}`)
3. Stripe дергает `POST /webhooks/stripe` -> проверяем подпись `Stripe-Signature` (HMAC-SHA256, endpoint secret) + сверяем сумму/заказ -> publish `payment.succeeded/failed`
4. shop consumer: `succeeded -> paid + qty-=, reserved-=` / `failed -> cancelled + reserved-=`
TTL `pending_payment` 15 мин. Все события с `event_id`, дедуп через `processed_events`, DLQ `vibemarket.dlx`.

## Запуск
```bash
docker compose up --build
# auth: :8001, shop: :8002, pay: :8003, UI: :8004, rabbit: :15672
```

## Тесты
```bash
pip install -r requirements.txt
make test-auth test-shop test-pay test-front
```

## Stripe

```bash
STRIPE_ENABLED=true STRIPE_SECRET_KEY=sk_test_... STRIPE_WEBHOOK_SECRET=whsec_... docker compose up --build
```

- Сессия: `mode=payment`, суммы в копейках (`100.00 RUB -> 10000`), `client_reference_id + metadata[order_id]`, заголовок `Idempotence-Key: order-{id}`.
- В кабинете (или `stripe listen`) направить события `checkout.session.completed`, `checkout.session.expired`, `checkout.session.async_payment_failed` на `https://<твой-домен>/webhooks/stripe`.
- Без ключей (`STRIPE_ENABLED=false`) сервис работает в dev-режиме: платежи `pending` без сессии.
- После оплаты: `POST /payments/by-order/{oid}/sync` (перепроверка после `success_url`, создает сессию если ее нет), отмена: `POST /payments/by-order/{oid}/cancel` (expire сессии в Stripe).
- Внимание: таблица `payments` — колонки `provider_payment_id (cs_...)/pay_url`; при старом volume нужен `docker compose down -v`.

## Что добавить по команде
- роли `buyer/admin` в auth, `Shipment` сущность
