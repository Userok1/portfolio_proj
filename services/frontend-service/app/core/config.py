from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    AUTH_API_URL: str = "http://localhost:8001"
    SHOP_API_URL: str = "http://localhost:8002"
    PAY_API_URL: str = "http://localhost:8003"
    SESSION_SECRET: str = "dev-frontend-secret"
    SESSION_TTL_H: int = 24

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
