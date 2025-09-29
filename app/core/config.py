from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    CEREBRAS_API_KEY: str # Ditambahkan kembali
    NVIDIA_API_KEY: str   # Dipertahankan
    GITHUB_TOKEN: str

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
