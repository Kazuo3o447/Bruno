#!/usr/bin/env python3
"""
Manuelle Ausführung der Datenbank-Migration für lokale Entwicklung.
Dieses Skript erstellt die market_candles Tabelle direkt.
"""

import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Lokale Datenbank-URL
LOCAL_DB_URL = "postgresql+asyncpg://bruno:bruno_secret@localhost:5432/bruno_trading"

async def create_market_candles_table():
    """Erstellt die market_candles Tabelle manuell."""
    
    # Engine mit lokaler URL erstellen
    engine = create_async_engine(
        LOCAL_DB_URL,
        echo=True,
        pool_size=5,
        max_overflow=5
    )
    
    try:
        async with engine.begin() as conn:
            print("Überprüfe ob market_candles Tabelle existiert...")
            
            # Prüfe ob Tabelle existiert
            result = await conn.execute(
                text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'market_candles'
                );
                """)
            )
            table_exists = result.scalar()
            
            if table_exists:
                print("✅ market_candles Tabelle existiert bereits")
                return
            
            print("❌ market_candles Tabelle existiert nicht. Erstelle sie...")
            
            # Erstelle die market_candles Tabelle
            await conn.execute(
                text("""
                CREATE TABLE market_candles (
                    time TIMESTAMP WITH TIME ZONE NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    open FLOAT NOT NULL,
                    high FLOAT NOT NULL,
                    low FLOAT NOT NULL,
                    close FLOAT NOT NULL,
                    volume FLOAT NOT NULL,
                    PRIMARY KEY (time, symbol)
                );
                """)
            )
            
            # Erstelle Indexe
            await conn.execute(
                text("""
                CREATE INDEX idx_market_candles_symbol_time 
                ON market_candles (symbol, time);
                """)
            )
            
            await conn.execute(
                text("""
                CREATE INDEX idx_market_candles_time 
                ON market_candles (time);
                """)
            )
            
            # Erstelle TimescaleDB Hypertable (falls TimescaleDB installiert ist)
            try:
                await conn.execute(
                    text("""
                    SELECT create_hypertable(
                        'market_candles', 
                        'time', 
                        if_not_exists => TRUE
                    );
                    """)
                )
                print("✅ TimescaleDB Hypertable erstellt")
            except Exception as e:
                print(f"⚠️  TimescaleDB Hypertable konnte nicht erstellt werden: {e}")
                print("ℹ️  Die Tabelle wird ohne TimescaleDB-Funktionen erstellt")
            
            print("✅ market_candles Tabelle erfolgreich erstellt")
            
    except Exception as e:
        print(f"❌ Fehler beim Erstellen der Tabelle: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    print("Starte manuelle Migration für market_candles Tabelle...")
    asyncio.run(create_market_candles_table())