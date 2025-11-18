from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App Settings the Validation """

    APP_NAME: str = "TRACKING SYSTEM"
    APP_VERSION: str = "1.0.0"   #First of it mist by Thabo :)
    DUBUG: bool = False

    #Connect to DHL ENDPOINT
    DHL_API_KEY: str
    DHL_API_SECRETE: str
    DHL_API_BASE_URL: str = "https://api-eu.dhl.com/track/shipments"
    DHL_DAILY_LIMIT: int   = 250

    #DATABASE sets
    DATABASE_URL: str  = "sqlite+aiosqlite:///./tracking_System.db" # current dir

    #Pushing set 
    BATCH_SIZE:int  = 25
    BATCH_DELAY: int  = 5 # seconds---> will change in due time 

    #mkdir for export 
    EXPORT_FOLDER: str  = "exprts"
    MAX_UPLOAD_SIZE: int  = 10485760 # 10mb     x  = 10/MAX_UPLOAD_SIZE
    ALLOWED_EXTENTIONS: List[str] = [".csv","xlsx","xls"]

#CORS
ALLOWED_ORIGINS:str = "http://localhost:3000,http://localhost:8080"

model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=True,
    extra="ignore"
)

@property
def cors_origin(self) -> List[str]:
    return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]  # string management delimiter focuses- comma
@property
def dhl_auth_header(self) -> dict:
    """DHL API Auth header"""
    return {
        "DHL-API-Key":self.DHL_API_KEY
    }



@lru_cache()
def get_settings() -> Settings:
    """
    This ensure that single instance of lru_cache is evoked per run(Sington or dependency injection pattern)
    """
    return Settings()
    
