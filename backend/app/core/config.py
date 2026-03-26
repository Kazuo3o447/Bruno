from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_USER: str = "bruno"
    DB_PASS: str = "bruno_secret"
    DB_NAME: str = "bruno_trading"
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    
    # Ollama (natively on Windows host by default)
    OLLAMA_HOST: str = "http://host.docker.internal:11434"
    
    # API
    API_V1_STR: str = "/api/v1"
    
    # External APIs
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_SECRET: Optional[str] = None
    CRYPTOPANIC_API_KEY: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

