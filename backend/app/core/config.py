from typing import Optional
from pydantic import model_validator
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
    
    # LLM Provider (Phase C)
    LLM_PROVIDER: str = "ollama"  # ollama | cloud
    DEEPSEEK_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    
    # API
    API_V1_STR: str = "/api/v1"
    
    # External APIs
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_SECRET: Optional[str] = None
    CRYPTOPANIC_API_KEY: Optional[str] = None
    FRED_API_KEY: Optional[str] = None

    # Macro Data Fallback
    ALPHA_VANTAGE_API_KEY: Optional[str] = None  # https://www.alphavantage.co/support/#api-key

    # Reddit OAuth (App-Only, kein User-Login)
    # App anlegen: https://www.reddit.com/prefs/apps → Typ "script"
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None

    # StockTwits (optional, leer lassen = wird übersprungen)
    STOCKTWITS_API_KEY: Optional[str] = None

    # HuggingFace Token für schnellere Model-Downloads
    # https://huggingface.co/settings/tokens → Read-Token
    HF_TOKEN: Optional[str] = None
    
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
    
    # Kapitalschutz — UNVERÄNDERLICH
    MAX_LEVERAGE: float = 1.0        # Kein Kredit. Niemals über 1.0.
    SIMULATED_CAPITAL_EUR: float = 500.0  # Startkapital für DRY_RUN Portfolio
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def _validate_capital_safety(self):
        if self.MAX_LEVERAGE > 1.0:
            raise ValueError("MAX_LEVERAGE must not exceed 1.0")
        if self.SIMULATED_CAPITAL_EUR < 10:
            raise ValueError("SIMULATED_CAPITAL_EUR must be at least 10 EUR")
        return self


settings = Settings()

