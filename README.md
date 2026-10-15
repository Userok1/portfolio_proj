# MyMarket — e-commerce микроcервисы (портфолио)
Физтовары. 4 сервиса, общение только через RabbitMQ. Эквайринг — Stripe.

## Сервисы
- `auth-service :8001` — register/login/refresh/logout, `GET /users/me`, `POST /auth/introspect`
- `shop-service :8002` — `GET /products`, `POST /cart/items`, `POST /orders` (резерв стока + `order.created`), `GET /orders/my`. Создание товара требует авторизации.
- `payment-service :8003` — `GET /payments/{id}`, `GET /payments/by-order/{oid}` (там `pay_url`), `POST /payments/by-order/{oid}/sync|cancel`, `POST /webhooks/stripe`
- `frontend-service :8004` — BFF на Jinja2: витрина, корзина, заказы, оплата, админка товаров. Сессии серверные (в памяти), JWT в браузер не уходят. Админка MVP: любой залогиненный (ролей нет).

Auth проверяется через `POST auth:8000/auth/introspect` по `httpx` (без shared JWT-валидации).

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
