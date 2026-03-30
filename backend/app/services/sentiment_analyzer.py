import logging
import asyncio
import os
from typing import Dict, Any, List, Optional
from transformers import pipeline

# HuggingFace Login für schnellere Model-Downloads (optional)
_hf_token = os.getenv("HF_TOKEN")
if _hf_token:
    try:
        from huggingface_hub import login
        login(token=_hf_token, add_to_git_credential=False)
    except ImportError:
        pass  # huggingface_hub nicht installiert, ignorieren

class SentimentAnalyzer:
    """
    NLP-Sentiment-Analyzer mit non-blocking Inference via asyncio.to_thread.
    Nutzt FinBERT, CryptoBERT und BART-MNLI Zero-Shot Classification.
    """
    def __init__(self):
        self.logger = logging.getLogger("sentiment_analyzer")
        self._finbert = None
        self._cryptobert = None
        self._zero_shot = None
        
        # Labels für den Zero-Shot Classifier (Schritt 1: Der Bouncer)
        self.labels = ["Regulatory", "Macro", "Infrastructure", "Opinion"]
        
    def _init_finbert(self):
        """Lazy Load FinBERT (ProsusAI) für Makro-Daten."""
        if self._finbert is None:
            self.logger.info("Lade FinBERT (ProsusAI/finbert)...")
            self._finbert = pipeline("sentiment-analysis", model="ProsusAI/finbert")
        return self._finbert
        
    def _init_cryptobert(self):
        """Lazy Load CryptoBERT (ElKulako/cryptobert) für Krypto-Daten."""
        if self._cryptobert is None:
            self.logger.info("Lade CryptoBERT (ElKulako/cryptobert)...")
            self._cryptobert = pipeline("sentiment-analysis", model="ElKulako/cryptobert")
        return self._cryptobert

    def _init_zero_shot(self):
        """Lazy Load Zero-Shot Classifier (facebook/bart-large-mnli)."""
        if self._zero_shot is None:
            self.logger.info("Lade Zero-Shot Classifier (facebook/bart-large-mnli)...")
            self._zero_shot = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
        return self._zero_shot

    async def classify_headline(self, text: str) -> Dict[str, Any]:
        """Klassifiziert News-Headlines non-blocking via asyncio.to_thread."""
        try:
            model = self._init_zero_shot()
            # Non-blocking Inference via to_thread (Schritt 1)
            result = await asyncio.to_thread(model, text, candidate_labels=self.labels)
            return {
                "top_label": result['labels'][0],
                "confidence": result['scores'][0],
                "all_labels": dict(zip(result['labels'], result['scores']))
            }
        except Exception as e:
            self.logger.error(f"Fehler in Zero-Shot Klassifizierung: {e}")
            return {"top_label": "error", "confidence": 0.0}

    async def analyze_with_filter(self, text: str, mode: str = "macro") -> Optional[Dict[str, Any]]:
        """
        Hauptmethode für die Analyse: 
        Kombiniert Klassifizierung und Sentiment-Analyse mit der Bouncer-Logik.
        """
        # 1. Zero-Shot Klassifizierung (Der Bouncer)
        classification = await self.classify_headline(text)
        label = classification["top_label"]
        
        # 2. Sentiment-Analyse
        sentiment = await self.analyze_macro(text) if mode == "macro" else await self.analyze_crypto(text)
            
        # 3. RAUSCHFILTER-LOGIK (Schritt 1)
        # WENN Label == "Opinion" UND abs(Score) < 0.75 -> Verwerfen
        if label == "Opinion" and abs(sentiment["score"]) < 0.75:
            self.logger.info(f"BOUNCER: News verworfen (Rauschen): {text[:60]}... (Label: {label}, Score: {sentiment['score']})")
            return None
            
        # 4. Ergebnis anreichern
        sentiment["classification"] = label
        sentiment["class_confidence"] = classification["confidence"]
        return sentiment

    async def analyze_macro(self, text: str) -> Dict[str, Any]:
        """Analyse eines Texts mit FinBERT (non-blocking)."""
        try:
            model = self._init_finbert()
            result = await asyncio.to_thread(model, text)
            res = result[0]
            score = 1.0 if res['label'] == 'positive' else -1.0 if res['label'] == 'negative' else 0.0
            return {"score": score, "confidence": res['score'], "label": res['label'], "model": "FinBERT"}
        except Exception as e:
            self.logger.error(f"FinBERT Fehler: {e}")
            return {"score": 0.0, "confidence": 0.0, "label": "error"}

    async def analyze_crypto(self, text: str) -> Dict[str, Any]:
        """Analyse eines Texts mit CryptoBERT (non-blocking)."""
        try:
            model = self._init_cryptobert()
            result = await asyncio.to_thread(model, text)
            res = result[0]
            label = res['label'].lower()
            score = 1.0 if "bullish" in label else -1.0 if "bearish" in label else 0.0
            return {"score": score, "confidence": res['score'], "label": res['label'], "model": "CryptoBERT"}
        except Exception as e:
            self.logger.error(f"CryptoBERT Fehler: {e}")
            return {"score": 0.0, "confidence": 0.0, "label": "error"}

    async def analyze_batch(self, texts: List[str], mode: str = "crypto") -> List[float]:
        """Analysiert eine Liste von Texten parallel und gibt die Scores zurück."""
        if not texts:
            return []
        
        tasks = []
        for text in texts:
            if mode == "crypto":
                tasks.append(self.analyze_crypto(text))
            else:
                tasks.append(self.analyze_macro(text))
                
        results = await asyncio.gather(*tasks)
        return [r["score"] for r in results]

# Singleton Instance
analyzer = SentimentAnalyzer()

