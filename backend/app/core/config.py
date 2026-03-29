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
    FRED_API_KEY: Optional[str] = None
    
    # Bybit Execution (Phase D — jetzt vorbereiten)
    BYBIT_API_KEY: Optional[str] = None
    BYBIT_SECRET: Optional[str] = None
    BYBIT_MODE: str = "demo"   # "demo" = api-demo.bybit.com | "live" = api.bybit.com
                               # NIEMALS auf "live" ohne bestandenen Backtest
    LIVE_TRADING_APPROVED: bool = False

    # Glassnode On-Chain (Phase C)
    GLASSNODE_API_KEY: Optional[str] = None

    # CoinGlass (Phase B — nach 4 Wochen DRY_RUN)
    COINGLASS_API_KEY: Optional[str] = None

    # Telegram Notifications (Phase B)
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    
    # Trading Mode
    DRY_RUN: bool = True
    
    # Risk & Learning
    DAILY_LOSS_LIMIT_PCT: float = 0.02      # 2% des Kontos — Hard Stop
    FAILURE_WATCH_EXPIRY_TRADES: int = 20    # Nach N Trades verfällt ein Failure Watch
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

