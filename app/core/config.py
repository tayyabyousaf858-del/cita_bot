"""Application configuration using pydantic-settings."""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    ENVIRONMENT: str = "production"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Admin
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    ADMIN_TELEGRAM_ID: int

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:80",
        "http://frontend:3000",
    ]

    # Playwright
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT: int = 30000

    # Monitoring
    POLL_INTERVAL_NORMAL_MIN: int = 30
    POLL_INTERVAL_NORMAL_MAX: int = 60
    POLL_INTERVAL_HIGH_MIN: int = 10
    POLL_INTERVAL_HIGH_MAX: int = 25
    MAX_CONCURRENT_WORKERS: int = 5

    # Firebase (optional)
    FIREBASE_CREDENTIALS_PATH: str = "/app/firebase-credentials.json"
    FIREBASE_PROJECT_ID: str = ""


settings = Settings()
