import asyncio
import hashlib
import logging
import os
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
import feedparser
import httpx
from bs4 import BeautifulSoup

from .sentiment_analyzer import analyzer

logger = logging.getLogger("news_ingestion")


class NewsIngestionService:
    """
    Privacy-First Multi-Source News Ingestion with Strict Deduplication.
    Zero Tolerance for Heuristics. BTC-Filter enforced.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("news_ingestion")
        
        # Deduplication Guard - SHA256 Hash Set
        self._processed_hashes: Set[str] = set()
        self._hash_deque = deque(maxlen=3000)  # Rolling window for memory management
        
        # API Keys from Environment
        self.cryptopanic_api_key = os.getenv("CRYPTOPANIC_API_KEY")
        
        # HTTP Client with proper headers
        self._http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "Bruno-Institutional-News-Aggregator/1.0"}
        )
        
        # RSS Feed URLs
        self.rss_feeds = [
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://cointelegraph.com/rss"
        ]
        
        # Statistics
        self.stats = {
            "total_processed": 0,
            "btc_filtered": 0,
            "deduped": 0,
            "sentiment_scored": 0,
            "cryptopanic_errors": 0,
            "rss_errors": 0,
            "fallback_errors": 0
        }

    def _generate_hash(self, title: str, timestamp: Optional[str] = None, url: Optional[str] = None) -> str:
        """
        Generate SHA256 hash for deduplication.
        Priority: title + timestamp > title + url > title
        """
        hash_input = title.lower().strip()
        
        if timestamp:
            hash_input += f"_{timestamp}"
        elif url:
            hash_input += f"_{url}"
            
        return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

    def _is_btc_related(self, title: str, content: str) -> bool:
        """
        Strict BTC/Bitcoin filter - case insensitive.
        """
        combined_text = (title + " " + content).lower()
        return "btc" in combined_text or "bitcoin" in combined_text

    def _strip_html(self, text: str) -> str:
        """
        Strip all HTML tags from text content.
        """
        if not text:
            return ""
        
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)

    async def process_news_item(self, title: str, content: str, timestamp: Optional[str] = None, 
                              url: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Process a single news item through the complete pipeline:
        1. BTC Filter
        2. Deduplication 
        3. Sentiment Analysis
        """
        self.stats["total_processed"] += 1
        
        # Step 1: BTC Filter
        if not self._is_btc_related(title, content):
            self.stats["btc_filtered"] += 1
            self.logger.debug(f"BTC Filter: Non-BTC news discarded - {title[:50]}...")
            return None
        
        # Step 2: Deduplication
        news_hash = self._generate_hash(title, timestamp, url)
        
        if news_hash in self._processed_hashes:
            self.stats["deduped"] += 1
            self.logger.debug(f"Deduplication: Duplicate news discarded - {title[:50]}...")
            return None
        
        # Add to processed sets
        self._processed_hashes.add(news_hash)
        self._hash_deque.append(news_hash)
        
        # Step 3: Clean content
        clean_content = self._strip_html(content)
        
        # Step 4: Sentiment Analysis
        try:
            sentiment_result = await analyzer.analyze_with_filter(clean_content, mode="crypto")
            
            if sentiment_result is None:
                self.logger.debug(f"Sentiment Bouncer: News discarded as noise - {title[:50]}...")
                return None
                
            self.stats["sentiment_scored"] += 1
            
            # Map sentiment to standardized format
            score = sentiment_result["score"]
            if score > 0.3:
                sentiment_label = "bullish"
            elif score < -0.3:
                sentiment_label = "bearish"
            else:
                sentiment_label = "neutral"
            
            result = {
                "title": title,
                "content": clean_content,
                "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
                "url": url,
                "sentiment": sentiment_label,
                "sentiment_score": score,
                "confidence": sentiment_result.get("confidence", 0.0),
                "classification": sentiment_result.get("classification", "unknown"),
                "source": metadata.get("source", "unknown") if metadata else "unknown",
                "metadata": metadata or {}
            }
            
            self.logger.info(f"News Processed: {sentiment_label} ({score:.3f}) - {title[:50]}...")
            return result
            
        except Exception as e:
            self.logger.error(f"Sentiment analysis failed for news item: {e}")
            return None

    async def fetch_cryptopanic_news(self) -> List[Dict[str, Any]]:
        """
        Data Source A: CryptoPanic API - Market Pulse
        Polling every 60 seconds.
        """
        if not self.cryptopanic_api_key:
            self.logger.warning("CRYPTOPANIC_API_KEY not configured")
            return []
        
        try:
            url = f"https://cryptopanic.com/api/v1/posts/?auth_token={self.cryptopanic_api_key}&currencies=BTC"
            response = await self._http_client.get(url)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("results", []):
                # Extract required fields
                title = item.get("title", "")
                content = item.get("content", title)  # Fallback to title if no content
                timestamp = item.get("published_at", "")
                url = item.get("url", "")
                
                # Pre-scoring metadata
                votes = item.get("votes", {})
                positive_votes = votes.get("positive", 0)
                negative_votes = votes.get("negative", 0)
                vote_score = positive_votes - negative_votes
                
                metadata = {
                    "source": "cryptopanic",
                    "vote_score": vote_score,
                    "positive_votes": positive_votes,
                    "negative_votes": negative_votes,
                    "categories": item.get("categories", [])
                }
                
                processed = await self.process_news_item(title, content, timestamp, url, metadata)
                if processed:
                    results.append(processed)
            
            return results
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                self.logger.warning("CryptoPanic API rate limit hit (429) - will retry")
            else:
                self.logger.error(f"CryptoPanic API error: {e}")
            self.stats["cryptopanic_errors"] += 1
            return []
        except Exception as e:
            self.logger.error(f"CryptoPanic fetch failed: {e}")
            self.stats["cryptopanic_errors"] += 1
            return []

    async def fetch_free_crypto_news(self) -> List[Dict[str, Any]]:
        """
        Data Source B: Free-Crypto-News (Open Source Aggregator)
        Polling every 120 seconds as fallback.
        """
        try:
            # Using a public crypto news API endpoint
            url = "https://api.freecryptoapi.com/v1/news"  # Example endpoint
            response = await self._http_client.get(url)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("news", []):
                title = item.get("title", "")
                content = item.get("description", title)
                timestamp = item.get("published_at", "")
                url = item.get("url", "")
                
                metadata = {
                    "source": "free_crypto_news",
                    "source_country": item.get("country", "unknown"),
                    "language": item.get("language", "en")
                }
                
                processed = await self.process_news_item(title, content, timestamp, url, metadata)
                if processed:
                    results.append(processed)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Free Crypto News fetch failed: {e}")
            self.stats["fallback_errors"] += 1
            return []

    async def fetch_rss_news(self) -> List[Dict[str, Any]]:
        """
        Data Source C: Direct RSS Scraper (Zero Latency)
        Parsing feeds every 30 seconds.
        """
        results = []
        
        for feed_url in self.rss_feeds:
            try:
                # Parse RSS feed
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries:
                    title = entry.get("title", "")
                    content = entry.get("summary", entry.get("description", title))
                    timestamp = entry.get("published", "")
                    url = entry.get("link", "")
                    
                    # Extract source from feed URL
                    source = "coindesk" if "coindesk" in feed_url else "cointelegraph"
                    
                    metadata = {
                        "source": source,
                        "feed_url": feed_url,
                        "author": entry.get("author", "unknown")
                    }
                    
                    processed = await self.process_news_item(title, content, timestamp, url, metadata)
                    if processed:
                        results.append(processed)
                        
            except Exception as e:
                self.logger.error(f"RSS feed error for {feed_url}: {e}")
                self.stats["rss_errors"] += 1
                continue
        
        return results

    async def start_ingestion_loop(self):
        """
        Main ingestion loop with different polling frequencies:
        - RSS: 30 seconds
        - CryptoPanic: 60 seconds  
        - Free Crypto News: 120 seconds (fallback)
        """
        self.logger.info("Starting News Ingestion Service")
        
        rss_counter = 0
        cryptopanic_counter = 0
        fallback_counter = 0
        
        while True:
            try:
                # RSS feeds every 30 seconds
                if rss_counter % 30 == 0:
                    rss_news = await self.fetch_rss_news()
                    self.logger.info(f"RSS: Processed {len(rss_news)} items")
                
                # CryptoPanic every 60 seconds
                if cryptopanic_counter % 60 == 0:
                    cryptopanic_news = await self.fetch_cryptopanic_news()
                    self.logger.info(f"CryptoPanic: Processed {len(cryptopanic_news)} items")
                
                # Free Crypto News every 120 seconds (fallback)
                if fallback_counter % 120 == 0:
                    fallback_news = await self.fetch_free_crypto_news()
                    self.logger.info(f"Free Crypto News: Processed {len(fallback_news)} items")
                
                # Increment counters
                rss_counter += 1
                cryptopanic_counter += 1
                fallback_counter += 1
                
                # Log statistics every 5 minutes
                if rss_counter % 300 == 0:
                    self.logger.info(f"News Ingestion Stats: {self.stats}")
                
                await asyncio.sleep(1)  # 1-second granularity
                
            except Exception as e:
                self.logger.error(f"News ingestion loop error: {e}")
                await asyncio.sleep(5)  # Brief pause on error

    def get_stats(self) -> Dict[str, Any]:
        """Return current ingestion statistics."""
        return {
            **self.stats,
            "hash_queue_size": len(self._hash_deque),
            "unique_hashes_stored": len(self._processed_hashes)
        }

    async def shutdown(self):
        """Cleanup resources."""
        await self._http_client.aclose()
        self.logger.info("News Ingestion Service shutdown complete")


# Global instance
news_ingestion_service = NewsIngestionService()
