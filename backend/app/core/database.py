from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Async URL Format für asyncpg
DATABASE_URL = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASS}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

# Async Engine mit optimierten Einstellungen für TimescaleDB
engine = create_async_engine(
    DATABASE_URL, 
    echo=False,  # Setze auf True für SQL-Debugging
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle alle Stunde
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency für FastAPI Endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialisiert die Datenbank (falls nötig)."""
    try:
        from sqlalchemy import text
        
        async with engine.begin() as conn:
            # Prüfe ob Extensions existieren
            await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"))
            await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        logger.info("Datenbank-Extensions vorhanden")
    except Exception as e:
        logger.error(f"Datenbank-Initialisierung fehlgeschlagen: {e}")
        # Nicht fatal - Extensions könnten über Alembic erstellt werden


async def close_db():
    """Schließt alle Datenbank-Verbindungen."""
    await engine.dispose()
    logger.info("Datenbank-Verbindungen geschlossen")
