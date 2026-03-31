#!/usr/bin/env python3
"""
Testet die Datenbank-Verbindung mit den aktuellen Konfigurationseinstellungen.
"""

import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Lade Umgebungsvariablen
from dotenv import load_dotenv
load_dotenv()

# Erstelle Engine mit aktuellen Einstellungen
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_USER = os.getenv("DB_USER", "bruno")
DB_PASS = os.getenv("DB_PASS", "bruno_secret")
DB_NAME = os.getenv("DB_NAME", "bruno_trading")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_size=5,
    max_overflow=5
)

async def test_connection():
    """Testet die Datenbank-Verbindung und Tabellen-Existenz."""
    
    try:
        print(f"Verbinde mit Datenbank: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        
        async with engine.connect() as conn:
            # Teste einfache Abfrage
            result = await conn.execute(text('SELECT 1'))
            print('✅ Datenbank-Verbindung erfolgreich')
            
            # Überprüfe ob market_candles Tabelle existiert
            result = await conn.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'market_candles')")
            )
            table_exists = result.scalar()
            print(f'✅ market_candles Tabelle existiert: {table_exists}')
            
            if table_exists:
                # Zähle Einträge in der Tabelle
                result = await conn.execute(
                    text("SELECT COUNT(*) FROM market_candles")
                )
                count = result.scalar()
                print(f'✅ market_candles hat {count} Einträge')
            
    except Exception as e:
        print(f'❌ Datenbank-Verbindungsfehler: {e}')
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    print("Teste Datenbank-Verbindung...")
    asyncio.run(test_connection())