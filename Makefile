.PHONY: up down logs test-auth test-shop test-pay test-front

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f

test-auth:
	cd services/auth-service && pytest -q

test-shop:
	cd services/shop-service && pytest -q

test-pay:
	cd services/payment-service && pytest -q

test-front:
	cd services/frontend-service && pytest -q
