"""
Configuration management using Pydantic Settings
Follows best practices for environment variable management
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    Uses .env file for local development
    """
    
    # Application Settings
    APP_NAME: str = "DHL Tracking System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # DHL API Configuration
    DHL_API_KEY: str = Field(..., description="DHL API Key")
    DHL_API_URL: str = "https://api-eu.dhl.com/track/shipments"
    DHL_DAILY_LIMIT: int = 250
    DHL_BATCH_SIZE: int = 25  # Process 25 tracking numbers per batch
    
    # Database Configuration
    DATABASE_URL: str = "sqlite:///./data/dhl_tracking.db"
    
    # File Processing Settings
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB and can be adjusted if one requeres
    ALLOWED_EXTENSIONS: list = [".csv", ".xlsx", ".xls"]
    UPLOAD_DIR: str = "./data/uploads"
    EXPORT_DIR: str = "./exports"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./data/app.log"
    
    class Config:
        env_file = ".env" #or env_file = ".env.example"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached settings instance
    Singleton pattern for configuration
    """
    return Settings()


# Export settings instance
settings = get_settings()
