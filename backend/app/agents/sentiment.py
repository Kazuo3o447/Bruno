import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies
from app.services.sentiment_analyzer import SentimentAnalyzer

class SentimentAgent(PollingAgent):
    """
    Sentiment Agent für News-Analyse.
    Nutzt FinBERT, CryptoBERT und Zero-Shot Classification für Sentiment-Scoring.
    """
    def __init__(self, deps: AgentDependencies):
        super().__init__("sentiment", deps)
        self.analyzer = SentimentAnalyzer()
        self.news_sources: List[str] = []
        self.last_analysis: Optional[Dict[str, Any]] = None

    async def setup(self) -> None:
        """Initialisiert den Sentiment Analyzer (Lazy-Load der Modelle)."""
        self.logger.info("SentimentAgent startet. Modelle werden bei Bedarf geladen.")
        # Test-Initialisierung um Fehler früh zu erkennen
        try:
            self.analyzer._init_zero_shot()
            self.logger.info("Zero-Shot Classifier initialisiert.")
        except Exception as e:
            self.logger.warning(f"Zero-Shot Init (lazy): {e}")

    def get_interval(self) -> float:
        """Alle 60 Sekunden News prüfen/analysieren."""
        return 60.0

    async def process(self) -> None:
        """
        Hauptverarbeitung: Sammelt und analysiert News-Sentiment.
        Publiziert Ergebnisse an Redis für andere Agenten.
        """
        try:
            # TODO: News von RSS/Twitter/API abrufen
            # Für jetzt: Dummy/Test-Analyse
            sample_headlines = [
                "Bitcoin surges as institutional investors pile in",
                "Fed signals potential rate cuts in 2024",
                "Crypto markets showing mixed signals today"
            ]

            sentiment_scores = []
            for headline in sample_headlines:
                result = await self.analyzer.analyze_with_filter(headline, mode="macro")
                if result:
                    sentiment_scores.append(result)

            if sentiment_scores:
                # Aggregierten Score berechnen
                avg_score = sum(s["score"] for s in sentiment_scores) / len(sentiment_scores)
                avg_confidence = sum(s["confidence"] for s in sentiment_scores) / len(sentiment_scores)

                self.last_analysis = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "average_score": round(avg_score, 3),
                    "average_confidence": round(avg_confidence, 3),
                    "samples_analyzed": len(sentiment_scores),
                    "interpretation": "bullish" if avg_score > 0.3 else "bearish" if avg_score < -0.3 else "neutral"
                }

                # An Redis publizieren für Quant/Risk Agenten
                await self.deps.redis.set_cache(
                    "bruno:sentiment:aggregate",
                    self.last_analysis,
                    ttl=300
                )

                self.logger.info(f"Sentiment-Update: {self.last_analysis['interpretation']} (Score: {avg_score:.2f})")

        except Exception as e:
            self.logger.error(f"Sentiment-Analyse fehlgeschlagen: {e}")
            raise

    async def get_last_analysis(self) -> Optional[Dict[str, Any]]:
        """Gibt die letzte Analyse zurück (für API-Zugriff)."""
        return self.last_analysis
