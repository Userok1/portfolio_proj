from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/auth_db"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALG: str = "HS256"
    ACCESS_TTL_MIN: int = 15
    REFRESH_TTL_DAYS: int = 30

    model_config = SettingsConfigDict(
        env_file=".env"
    )


settings = Settings()
