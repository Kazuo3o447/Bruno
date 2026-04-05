"""
Telegram Bot — Bruno Trading Bot

Bidirektional:
- Sendet: Trade-Alerts, Vetos, Daily Summary, Kritische Warnungen
- Empfängt: Emergency Stop, Pause, Status-Abfrage via Inline-Buttons

Polling-Modus: Funktioniert auf Windows/WSL2 und Ubuntu nativ.
Startet ohne Keys (graceful degradation).

Alert-Hierarchie (aus BRUNO_REVIEW.md):
  KRITISCH  → sofort senden
  HOCH      → sofort senden
  MITTEL    → gebündelt 1×/Stunde
  INFO      → nur Daily Report
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Callable
from enum import Enum

logger = logging.getLogger("telegram_bot")


class AlertLevel(Enum):
    KRITISCH = "kritisch"
    HOCH = "hoch"
    MITTEL = "mittel"
    INFO = "info"


class BrunoTelegramBot:

    def __init__(self, token: Optional[str], chat_id: Optional[str],
                 redis_client=None):
        self.token = token
        self.chat_id = chat_id
        self.redis = redis_client
        self._bot = None
        self._app = None
        self._running = False
        self._emergency_stop_callback: Optional[Callable] = None
        self._pause_callback: Optional[Callable] = None
        self._hourly_buffer: list = []  # Mittlere Alerts puffern
        self._last_hourly_flush: float = 0.0

    def set_callbacks(self,
                      emergency_stop: Callable,
                      pause: Callable) -> None:
        """Registriert Callbacks für Bot-Befehle."""
        self._emergency_stop_callback = emergency_stop
        self._pause_callback = pause

    async def start(self) -> bool:
        """Startet den Bot. Gibt False zurück wenn keine Keys."""
        if not self.token or not self.chat_id:
            logger.warning(
                "Telegram: Kein Token/Chat-ID — Bot inaktiv. "
                "Keys in .env eintragen um zu aktivieren."
            )
            return False

        try:
            from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
            from telegram.ext import (
                Application, CallbackQueryHandler,
                CommandHandler, ContextTypes
            )

            self._app = (
                Application.builder()
                .token(self.token)
                .build()
            )
            self._bot = self._app.bot

            # Callback-Handler für Inline-Buttons registrieren
            self._app.add_handler(
                CallbackQueryHandler(self._handle_button)
            )
            self._app.add_handler(
                CommandHandler("status", self._handle_status_command)
            )
            self._app.add_handler(
                CommandHandler("stop", self._handle_stop_command)
            )

            # Polling im Hintergrund starten
            await self._app.initialize()
            await self._app.start()
            await self._app.updater.start_polling(
                drop_pending_updates=True
            )

            self._running = True
            logger.info("Telegram Bot gestartet (Polling-Modus)")

            # Startup-Nachricht
            await self.send_startup_message()
            return True

        except ImportError:
            logger.error(
                "python-telegram-bot nicht installiert. "
                "pip install python-telegram-bot==20.8"
            )
            return False
        except Exception as e:
            logger.error(f"Telegram Start Fehler: {e}")
            return False

    async def stop(self) -> None:
        if self._app and self._running:
            try:
                await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
            except Exception as e:
                logger.warning(f"Telegram Stop Fehler: {e}")
            self._running = False

    # ─────────────────────────────────────────────────────────
    # Button-Handler
    # ─────────────────────────────────────────────────────────

    async def _handle_button(self, update, context) -> None:
        """Verarbeitet Klicks auf Inline-Buttons."""
        query = update.callback_query
        await query.answer()  # Telegram erwartet sofortige Antwort

        # Nur autorisierte Chat-ID darf steuern
        if str(update.effective_chat.id) != str(self.chat_id):
            await query.answer("Nicht autorisiert.", show_alert=True)
            return

        data = query.data
        user = query.from_user.username or query.from_user.first_name

        if data == "emergency_stop":
            await query.edit_message_text(
                f"🔴 EMERGENCY STOP ausgelöst von @{user}\n"
                f"Alle Positionen werden geschlossen..."
            )
            if self._emergency_stop_callback:
                asyncio.create_task(self._emergency_stop_callback())

        elif data == "pause_4h":
            await query.edit_message_text(
                f"⏸️ Bot pausiert für 4 Stunden von @{user}"
            )
            if self._pause_callback:
                asyncio.create_task(self._pause_callback(hours=4))

        elif data == "pause_24h":
            await query.edit_message_text(
                f"⏸️ Bot pausiert für 24 Stunden von @{user}"
            )
            if self._pause_callback:
                asyncio.create_task(self._pause_callback(hours=24))

        elif data == "resume":
            await query.edit_message_text(
                f"▶️ Bot fortgesetzt von @{user}"
            )
            if self._pause_callback:
                asyncio.create_task(self._pause_callback(hours=0))

        elif data == "status":
            status_text = await self._build_status_text()
            await query.edit_message_text(status_text)

    async def _handle_status_command(self, update, context) -> None:
        if str(update.effective_chat.id) != str(self.chat_id):
            await update.message.reply_text("Nicht autorisiert.")
            return
        status_text = await self._build_status_text()
        await update.message.reply_text(status_text)

    async def _handle_stop_command(self, update, context) -> None:
        if str(update.effective_chat.id) != str(self.chat_id):
            await update.message.reply_text("Nicht autorisiert.")
            return
        await update.message.reply_text(
            "⚠️ Bitte nutze den [🔴 EMERGENCY STOP] Button "
            "in einer Alert-Nachricht, oder sende /confirm_stop"
        )

    async def _build_status_text(self) -> str:
        """Baut den aktuellen Status-Text aus Redis."""
        if not self.redis:
            return "Status nicht verfügbar (kein Redis)"

        grss_data = await self.redis.get_cache("bruno:context:grss") or {}
        portfolio = await self.redis.get_cache("bruno:portfolio:state") or {}
        position = await self.redis.get_cache("bruno:position:BTCUSDT") or {}

        grss = grss_data.get("GRSS_Score", "N/A")
        veto = grss_data.get("Veto_Active", True)
        capital = portfolio.get("capital_eur", 0)
        daily_pnl = portfolio.get("daily_pnl_eur", 0)
        pos_status = position.get("status", "none")
        pos_side = position.get("side", "")

        return (
            f"📊 *Bruno Status*\n"
            f"GRSS: {grss} | Veto: {'⛔ JA' if veto else '✅ NEIN'}\n"
            f"Kapital: {capital:.2f} EUR\n"
            f"Heute P&L: {daily_pnl:+.2f} EUR\n"
            f"Position: {pos_status} {pos_side.upper() if pos_side else ''}"
        )

    # ─────────────────────────────────────────────────────────
    # Senden
    # ─────────────────────────────────────────────────────────

    async def _send(self, text: str,
                    reply_markup=None,
                    parse_mode: str = "Markdown") -> bool:
        """Basis-Sendemethode mit Fehlerbehandlung."""
        if not self._bot or not self.chat_id:
            return False
        try:
            await self._bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            return True
        except Exception as e:
            logger.warning(f"Telegram Sende-Fehler: {e}")
            return False

    def _make_control_keyboard(self):
        """Erstellt Standard-Kontroll-Keyboard."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔴 EMERGENCY STOP", callback_data="emergency_stop"
                )
            ],
            [
                InlineKeyboardButton(
                    "⏸️ Pause 4H", callback_data="pause_4h"
                ),
                InlineKeyboardButton(
                    "⏸️ Pause 24H", callback_data="pause_24h"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 Status", callback_data="status"
                )
            ]
        ])

    def _make_trade_keyboard(self):
        """Keyboard für Trade-Alerts."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔴 JETZT SCHLIESSEN", callback_data="emergency_stop"
                ),
                InlineKeyboardButton(
                    "📊 Status", callback_data="status"
                )
            ]
        ])

    # ─────────────────────────────────────────────────────────
    # Alert-Methoden
    # ─────────────────────────────────────────────────────────

    async def send_startup_message(self) -> None:
        keyboard = self._make_control_keyboard() if self._bot else None
        await self._send(
            "🤖 *Bruno Trading Bot gestartet*\n"
            "DRY_RUN aktiv — kein echtes Kapital.\n"
            "Verwende die Buttons für Steuerung.",
            reply_markup=keyboard
        )

    async def send_trade_entry(self, trade: dict) -> None:
        """Alert bei Trade-Eröffnung."""
        side_emoji = "🟢" if trade.get("side") == "long" else "🔴"
        text = (
            f"{side_emoji} *{trade.get('side', '').upper()} BTCUSDT*\n"
            f"Entry: ${trade.get('entry_price', 0):,.0f} | "
            f"Qty: {trade.get('quantity', 0):.3f} BTC\n"
            f"SL: ${trade.get('stop_loss_price', 0):,.0f} | "
            f"TP: ${trade.get('take_profit_price', 0):,.0f}\n"
            f"GRSS: {trade.get('grss_at_entry', 0):.1f} | "
            f"L2 Conf: {trade.get('layer2_confidence', 0):.0%}\n"
            f"_{trade.get('layer2_reasoning', '')[:100]}_"
        )
        keyboard = self._make_trade_keyboard() if self._bot else None
        await self._send(text, reply_markup=keyboard)

    async def send_trade_exit(self, trade: dict) -> None:
        """Alert bei Trade-Schließung."""
        pnl = trade.get("pnl_pct", 0)
        pnl_emoji = "✅" if pnl > 0 else "❌"
        reason = trade.get("exit_reason", "UNKNOWN")

        text = (
            f"{pnl_emoji} *{reason}* — {trade.get('side', '').upper()} BTCUSDT\n"
            f"Exit: ${trade.get('exit_price', 0):,.0f} | "
            f"Gehalten: {trade.get('hold_minutes', 0)} Min\n"
            f"P&L: {pnl:+.2%} | "
            f"Fees: -€{trade.get('fee_eur', 0):.3f}\n"
            f"MAE: {trade.get('mae_pct', 0):.2%} | "
            f"MFE: {trade.get('mfe_pct', 0):.2%}"
        )
        await self._send(text)

    async def send_veto_alert(self, reason: str, grss: float) -> None:
        """Alert wenn GRSS-Veto aktiv wird."""
        await self._send(
            f"⛔ *VETO AKTIV*\n"
            f"GRSS: {grss:.1f}\n"
            f"Grund: {reason}"
        )

    async def send_critical_alert(self, message: str) -> None:
        """Kritischer Alert — sofort, mit Kontroll-Keyboard."""
        keyboard = self._make_control_keyboard() if self._bot else None
        await self._send(
            f"🚨 *KRITISCH*\n{message}",
            reply_markup=keyboard
        )

    async def send_daily_summary(self, portfolio: dict) -> None:
        """Tägliche Zusammenfassung um 23:55 UTC."""
        total = portfolio.get("total_trades", 0)
        wins = portfolio.get("winning_trades", 0)
        wr = wins / total if total > 0 else 0
        daily_pnl = portfolio.get("daily_pnl_eur", 0)
        capital = portfolio.get("capital_eur", 0)
        initial = portfolio.get("initial_capital_eur", 500)
        total_return = (capital - initial) / initial

        keyboard = self._make_control_keyboard() if self._bot else None
        await self._send(
            f"📈 *Daily Summary*\n"
            f"Heute: {total} Trades | WR: {wr:.0%}\n"
            f"Tages P&L: {daily_pnl:+.2f} EUR\n"
            f"Kapital: {capital:.2f} EUR\n"
            f"Gesamt-Return: {total_return:+.1%}",
            reply_markup=keyboard
        )

    async def send_fomo_warning(self, retail_score: float) -> None:
        """FOMO-Warning aus Retail Sentiment."""
        await self._send(
            f"⚠️ *FOMO-WARNING*\n"
            f"Retail Score: {retail_score:.3f}\n"
            f"Reddit + StockTwits gleichzeitig extrem bullish.\n"
            f"Historisch: Top-Signal. Reversal-Risiko erhöht."
        )


# Singleton
_bot_instance: Optional[BrunoTelegramBot] = None


def get_telegram_bot() -> Optional[BrunoTelegramBot]:
    return _bot_instance


def init_telegram_bot(token: Optional[str],
                      chat_id: Optional[str],
                      redis_client=None) -> BrunoTelegramBot:
    global _bot_instance
    _bot_instance = BrunoTelegramBot(token, chat_id, redis_client)
    return _bot_instance
