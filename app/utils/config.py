"""
Configuration management using Pydantic Settings
"""
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "DHL Tracking System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # API
    API_V1_PREFIX: str = "/api/v1"          # ← THIS WAS MISSING
    PROJECT_NAME: str = "DHL Tracking API"  # ← also often used

    # DHL API
    DHL_API_KEY: str
    DHL_API_URL: str = "https://api-eu.dhl.com/track/shipments"
    DHL_DAILY_LIMIT: int = 250
    DHL_BATCH_SIZE: int = 10

    # Database
    DATABASE_URL: str = "sqlite:///./tracking.db"

    # File upload & export
    UPLOAD_DIR: str = "./data/uploads"
    EXPORT_DIR: str = "./exports"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS: List[str] = [".csv", ".xlsx", ".xls"]

    # Email
    SMTP_SERVER: str
    SMTP_PORT: int = 587
    FROM_EMAIL: str
    EMAIL_PASSWORD: str

    # Team leader emails (comma-separated string in .env)
    TEAM_LEADER_EMAILS: str = ""

    @field_validator("TEAM_LEADER_EMAILS")
    @classmethod
    def split_emails(cls, v: str) -> List[str]:
        if not v:
            return []
        return [email.strip() for email in v.split(",") if email.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()