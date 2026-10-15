from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/shop_db"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    AUTH_INTROSPECT_URL: str = "http://localhost:8001/auth/introspect"
    ORDER_TTL_MIN: int = 15

    model_config = SettingsConfigDict(
        env_file=".env"
    )


settings = Settings()
