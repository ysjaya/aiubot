from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import secrets
import os

class Settings(BaseSettings):
    DATABASE_URL: str
    CEREBRAS_API_KEY: str = ""
    NVIDIA_API_KEY: str = ""
    GITHUB_TOKEN: str = ""
    
    # API keys untuk web search
    SERPAPI_API_KEY: str = ""
    BING_API_KEY: str = ""
    
    # OAuth fields are optional since we now use Replit connector
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    SECRET_KEY: str = ""
    
    # Database pool configuration
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# Generate a secure secret key if not provided (for development only)
if not settings.SECRET_KEY:
    if os.getenv("REPL_ID"):  # Running in Replit
        settings.SECRET_KEY = secrets.token_urlsafe(32)
        print("⚠️ WARNING: Using auto-generated SECRET_KEY for development. Set SECRET_KEY in production!")
    else:  # Production
        raise ValueError("SECRET_KEY must be set in production environment")

# Logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cek ketersediaan API keys
if not settings.CEREBRAS_API_KEY:
    logger.warning("⚠️ CEREBRAS_API_KEY not configured - Cerebras integration will be limited")
if not settings.NVIDIA_API_KEY:
    logger.warning("⚠️ NVIDIA_API_KEY not configured - NVIDIA integration will be limited")
if not settings.SERPAPI_API_KEY:
    logger.debug("🔍 SERPAPI_API_KEY not configured - enhanced web search will be limited")
if not settings.BING_API_KEY:
    logger.debug("🔍 BING_API_KEY not configured - Bing search will be limited")
