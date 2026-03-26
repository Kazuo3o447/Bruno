import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DB_HOST: str = os.getenv("DB_HOST", "postgres")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("DB_USER", "bruno")
    POSTGRES_PASSWORD: str = os.getenv("DB_PASS", "bruno_secret")
    POSTGRES_DB: str = os.getenv("DB_NAME", "bruno_trading")
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    
    # Ollama (Windows Host) - Force override
    OLLAMA_HOST: str = "http://host.docker.internal:11434"
    
    def __post_init__(self):
        # Force override OLLAMA_HOST regardless of environment
        self.OLLAMA_HOST = "http://host.docker.internal:11434"
    
    # API
    API_V1_STR: str = "/api/v1"
    
    # Binance (optional für Paper Trading)
    BINANCE_API_KEY: Optional[str] = os.getenv("BINANCE_API_KEY")
    BINANCE_SECRET: Optional[str] = os.getenv("BINANCE_SECRET")
    
    class Config:
        env_file = ".env"


settings = Settings()

# Force override OLLAMA_HOST for Windows-Hybrid architecture
settings.OLLAMA_HOST = "http://host.docker.internal:11434"
