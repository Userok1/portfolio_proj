from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/billing_db"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    AUTH_INTROSPECT_URL: str = "http://localhost:8001/auth/introspect"
    # Stripe (Checkout Sessions: hosted page + webhooks)
    STRIPE_ENABLED: bool = False
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_SUCCESS_URL: str = "http://localhost:8004/payment/success?session_id={CHECKOUT_SESSION_ID}"
    STRIPE_CANCEL_URL: str = "http://localhost:8002/orders/cancelled"
    STRIPE_CURRENCY: str = "rub"
    STRIPE_API_URL: str = "https://api.stripe.com"

    model_config = SettingsConfigDict(
        env_file=".env"
    )


settings = Settings()
