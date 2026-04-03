import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

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

# Legacy compatibility - SessionLocal alias for AsyncSessionLocal
SessionLocal = AsyncSessionLocal

ALEMBIC_INI_PATH = Path(__file__).resolve().parents[2] / "alembic.ini"
MIGRATION_LOCK_KEY_1 = 8421
MIGRATION_LOCK_KEY_2 = 20260402


def _build_alembic_config() -> Config:
    if not ALEMBIC_INI_PATH.exists():
        raise FileNotFoundError(f"Alembic config not found: {ALEMBIC_INI_PATH}")

    return Config(str(ALEMBIC_INI_PATH))


def _run_alembic_upgrade_head() -> None:
    """Runs Alembic migrations synchronously."""
    command.upgrade(_build_alembic_config(), "head")


async def _schema_needs_migration() -> bool:
    """Checks whether the database schema is missing required Bruno tables."""
    async with engine.connect() as conn:
        market_candles_exists = await conn.scalar(
            text("SELECT to_regclass('public.market_candles') IS NOT NULL")
        )
        alembic_version_exists = await conn.scalar(
            text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
        )

        if not market_candles_exists or not alembic_version_exists:
            return True

        current_version = await conn.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
        head_version = ScriptDirectory.from_config(_build_alembic_config()).get_current_head()
        return current_version != head_version


async def ensure_schema() -> None:
    """Ensures the database schema is migrated to the latest revision."""
    try:
        needs_migration = await _schema_needs_migration()
        if not needs_migration:
            logger.info("Datenbankschema ist bereits aktuell")
            return

        logger.info("Datenbankschema unvollständig oder veraltet. Starte Alembic upgrade head...")

        async with engine.connect() as conn:
            await conn.execute(
                text(f"SELECT pg_advisory_lock({MIGRATION_LOCK_KEY_1}, {MIGRATION_LOCK_KEY_2})")
            )
            try:
                await asyncio.to_thread(_run_alembic_upgrade_head)
            finally:
                await conn.execute(
                    text(f"SELECT pg_advisory_unlock({MIGRATION_LOCK_KEY_1}, {MIGRATION_LOCK_KEY_2})")
                )

        logger.info("Alembic-Migrationen erfolgreich ausgeführt")
    except Exception as e:
        logger.error(f"Datenbankschema-Migration fehlgeschlagen: {e}")
        raise


async def get_db() -> AsyncSession:
    """Dependency für FastAPI Endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialisiert die Datenbank und stellt das Schema sicher."""
    try:
        async with engine.begin() as conn:
            # Prüfe ob Extensions existieren
            await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"))
            await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        logger.info("Datenbank-Extensions vorhanden")
        await ensure_schema()
    except Exception as e:
        logger.error(f"Datenbank-Initialisierung fehlgeschlagen: {e}")
        raise


async def close_db():
    """Schließt alle Datenbank-Verbindungen."""
    await engine.dispose()
    logger.info("Datenbank-Verbindungen geschlossen")


def get_db_session_factory():
    """Dependency Injection Funktion für FastAPI."""
    return AsyncSessionLocal
