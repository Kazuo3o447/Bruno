"""
Macro Event Calendar for Bruno.

Provides a small institutional guardrail around high-impact events
such as FOMC, CPI and NFP.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import calendar
from typing import ClassVar, Dict, List, Optional


@dataclass(frozen=True)
class EventRule:
    name: str
    dates: List[str]
    time_utc: str
    pre_buffer_min: int
    post_buffer_min: int
    threshold_mult: float


class EventCalendar:
    """
    Statischer + dynamischer Makro-Event-Kalender.

    Zweck: Vor FOMC/CPI/NFP soll der Threshold angehoben werden,
    weil diese Events massive Volatilität verursachen und TA-Signale
    in den 30 Minuten davor wertlos sind.
    """

    FOMC_DATES: ClassVar[List[str]] = [
        "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
        "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
    ]

    @staticmethod
    def _first_friday(year: int, month: int) -> str:
        cal = calendar.monthcalendar(year, month)
        friday_index = calendar.FRIDAY
        for week in cal:
            if week[friday_index] != 0:
                return f"{year:04d}-{month:02d}-{week[friday_index]:02d}"
        return f"{year:04d}-{month:02d}-01"

    @staticmethod
    def _cpi_dates(year: int = 2026) -> List[str]:
        # Näherung: mittlerer Monat, ausreichend als statischer Guard.
        return [f"{year:04d}-{month:02d}-13" for month in range(1, 13)]

    @staticmethod
    def _nfp_dates(year: int = 2026) -> List[str]:
        return [EventCalendar._first_friday(year, month) for month in range(1, 13)]

    @classmethod
    def get_events(cls) -> List[EventRule]:
        """Return the events list with properly initialized dates."""
        return [
            EventRule(
                name="FOMC",
                dates=cls.FOMC_DATES,
                time_utc="18:00",
                pre_buffer_min=30,
                post_buffer_min=60,
                threshold_mult=1.5,
            ),
            EventRule(
                name="CPI",
                dates=cls._cpi_dates(2026),
                time_utc="12:30",
                pre_buffer_min=15,
                post_buffer_min=30,
                threshold_mult=1.3,
            ),
            EventRule(
                name="NFP",
                dates=cls._nfp_dates(2026),
                time_utc="12:30",
                pre_buffer_min=15,
                post_buffer_min=30,
                threshold_mult=1.3,
            ),
        ]

    @classmethod
    def get_active_event(cls) -> Optional[Dict[str, object]]:
        """Gibt das aktive Event zurück wenn wir im Buffer-Fenster sind."""
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")

        for event_type in cls.get_events():
            if today not in event_type.dates:
                continue

            event_time = datetime.strptime(
                f"{today} {event_type.time_utc}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=timezone.utc)

            pre_start = event_time - timedelta(minutes=event_type.pre_buffer_min)
            post_end = event_time + timedelta(minutes=event_type.post_buffer_min)

            if pre_start <= now <= post_end:
                return {
                    "event": event_type.name,
                    "time": event_time,
                    "pre_start": pre_start,
                    "post_end": post_end,
                    "threshold_mult": event_type.threshold_mult,
                }

        return None
