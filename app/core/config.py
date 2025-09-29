from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    CEREBRAS_API_KEY: str
    NVIDIA_API_KEY: str
    GITHUB_TOKEN: str
    
    # --- Tambahkan ini ---
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str
    SECRET_KEY: str

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
