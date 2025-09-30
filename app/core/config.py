from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import secrets
import os

class Settings(BaseSettings):
    DATABASE_URL: str
    CEREBRAS_API_KEY: str = ""
    NVIDIA_API_KEY: str = ""
    GITHUB_TOKEN: str = ""
    
    # OAuth fields are optional since we now use Replit connector
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    SECRET_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# Generate a secure secret key if not provided (for development only)
if not settings.SECRET_KEY:
    if os.getenv("REPL_ID"):  # Running in Replit
        settings.SECRET_KEY = secrets.token_urlsafe(32)
        print("⚠️ WARNING: Using auto-generated SECRET_KEY for development. Set SECRET_KEY in production!")
    else:  # Production
        raise ValueError("SECRET_KEY must be set in production environment")
