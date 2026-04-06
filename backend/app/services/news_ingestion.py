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
from .news_providers.free_crypto_news import free_crypto_news_client

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
        self.coinmarketcap_api_key = os.getenv("CMC_API_KEY")
        
        # HTTP Client with proper headers
        self._http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "Bruno-Institutional-News-Aggregator/1.0"}
        )
        
        # RSS Feed URLs - Maximum Coverage (Working Feeds Only)
        self.rss_feeds = [
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://cointelegraph.com/rss",
            "https://decrypt.co/feed"  # Additional crypto news (37 items)
        ]
        
        # Redis Client für Sentiment-Agent Integration
        self._redis_client = None
        
        # Statistics
        self.stats = {
            "total_processed": 0,
            "btc_filtered": 0,
            "deduped": 0,
            "sentiment_scored": 0,
            "cmc_errors": 0,
            "rss_errors": 0,
            "fallback_errors": 0
        }

    def set_redis_client(self, redis_client):
        """Set Redis client for integration with SentimentAgent."""
        self._redis_client = redis_client
        self.logger.info("Redis client für News Ingestion gesetzt")

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
            
            # Speichere in Redis für SentimentAgent
            await self._store_processed_news(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Sentiment analysis failed for news item: {e}")
            return None

    async def _store_processed_news(self, processed_news: Dict[str, Any]):
        """Speichere verarbeitete News in Redis für SentimentAgent."""
        if not self._redis_client:
            return
            
        try:
            # Speichere einzelne News-Items für Sentiment-Agent
            await self._redis_client.set_cache(
                f"bruno:news:item:{processed_news['title'][:50]}",
                processed_news,
                ttl=3600  # 1 Stunde
            )
            
            # Speichere Aggregat für schnellen Zugriff
            existing_items = await self._redis_client.get_cache("bruno:news:processed_items") or []
            existing_items.append({
                "title": processed_news["title"],
                "sentiment": processed_news["sentiment"],
                "sentiment_score": processed_news["sentiment_score"],
                "source": processed_news["source"],
                "timestamp": processed_news["timestamp"]
            })
            
            # Nur die letzten 50 Items behalten
            if len(existing_items) > 50:
                existing_items = existing_items[-50:]
            
            await self._redis_client.set_cache(
                "bruno:news:processed_items",
                existing_items,
                ttl=1800  # 30 Minuten
            )
            
        except Exception as e:
            self.logger.error(f"Failed to store processed news in Redis: {e}")

    async def fetch_coinmarketcap_data(self) -> List[Dict[str, Any]]:
        """
        CoinMarketCap Market Data API - Additional market metrics
        Polling every 60 seconds.
        """
        if not self.coinmarketcap_api_key:
            self.logger.warning("CMC_API_KEY not configured")
            return []
        
        try:
            # Get BTC market data
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            headers = {
                "X-CMC_PRO_API_KEY": self.coinmarketcap_api_key,
                "Accept": "application/json"
            }
            params = {
                "symbol": "BTC",
                "convert": "USD"
            }
            
            response = await self._http_client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            btc_data = data.get("data", {}).get("BTC", {})
            
            if not btc_data:
                self.logger.warning("No BTC data from CoinMarketCap")
                return []
            
            # Extract market metrics
            quote = btc_data.get("quote", {}).get("USD", {})
            market_data = {
                "source": "coinmarketcap",
                "price": quote.get("price", 0),
                "volume_24h": quote.get("volume_24h", 0),
                "market_cap": quote.get("market_cap", 0),
                "percent_change_1h": quote.get("percent_change_1h", 0),
                "percent_change_24h": quote.get("percent_change_24h", 0),
                "percent_change_7d": quote.get("percent_change_7d", 0),
                "market_cap_dominance": btc_data.get("market_cap_dominance", 0),
                "timestamp": btc_data.get("last_updated", "")
            }
            
            # Store in Redis for other agents
            if self._redis_client:
                await self._redis_client.setex(
                    "market:coinmarketcap:btc",
                    300,  # 5 minutes TTL
                    json.dumps(market_data)
                )
            
            self.logger.info(f"CoinMarketCap data updated: Price=${market_data['price']:.2f}, 24h={market_data['percent_change_24h']:.2f}%")
            return [market_data]
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self.logger.error("CoinMarketCap API key invalid (401)")
            elif e.response.status_code == 429:
                self.logger.warning("CoinMarketCap API rate limit hit (429)")
            else:
                self.logger.error(f"CoinMarketCap API error: {e}")
            self.stats["cmc_errors"] += 1
            return []
        except Exception as e:
            self.logger.error(f"CoinMarketCap fetch failed: {e}")
            self.stats["cmc_errors"] += 1
            return []

    async def fetch_free_crypto_news_tier3(self) -> List[Dict[str, Any]]:
        """
        Data Source B: Multiple Free APIs (Primary News Source)
        Polling every 120 seconds as supplementary source.
        """
        results = []
        
        # Try multiple free APIs in order of preference
        api_sources = [
            {
                "name": "cryptocompare",
                "url": "https://min-api.cryptocompare.com/data/v2/news/?lang=EN",
                "parser": self._parse_cryptocompare_news
            },
            {
                "name": "newsapi",
                "url": "https://newsapi.org/v2/everything?q=bitcoin&apiKey=demo",  # Demo key
                "parser": self._parse_newsapi_news
            },
            {
                "name": "jsonfeed",
                "url": "https://www.reddit.com/r/Bitcoin/hot.json",
                "parser": self._parse_reddit_news
            }
        ]
        
        for source in api_sources:
            try:
                response = await self._http_client.get(source["url"])
                response.raise_for_status()
                
                data = response.json()
                parsed_items = await source["parser"](data, source["name"])
                
                for item in parsed_items:
                    processed = await self.process_news_item(
                        item["title"], 
                        item["content"], 
                        item["timestamp"], 
                        item["url"], 
                        item["metadata"]
                    )
                    if processed:
                        results.append(processed)
                
                if results:  # If we got results from this API, break
                    self.logger.info(f"{source['name']}: {len(results)} BTC-related items processed")
                    break
                    
            except Exception as e:
                self.logger.warning(f"{source['name']} API failed: {e}")
                continue
        
        if not results:
            self.logger.warning("All free APIs failed - no news items processed")
        
        return results

    async def _parse_cryptocompare_news(self, data: Dict, source_name: str) -> List[Dict]:
        """Parse CryptoCompare news format."""
        items = data.get("Data", [])
        results = []
        
        for item in items:
            title = item.get("title", "")
            content = item.get("body", title)
            timestamp = str(item.get("published_on", ""))
            url = item.get("url", "")
            
            metadata = {
                "source": source_name,
                "source_api": "cryptocompare_free",
                "categories": item.get("categories", []),
                "image_url": item.get("imageurl", "")
            }
            
            results.append({
                "title": title,
                "content": content,
                "timestamp": timestamp,
                "url": url,
                "metadata": metadata
            })
        
        return results

    async def _parse_newsapi_news(self, data: Dict, source_name: str) -> List[Dict]:
        """Parse NewsAPI format."""
        items = data.get("articles", [])
        results = []
        
        for item in items:
            title = item.get("title", "")
            content = item.get("description", title)
            timestamp = item.get("publishedAt", "")
            url = item.get("url", "")
            
            metadata = {
                "source": source_name,
                "source_api": "newsapi_demo",
                "author": item.get("author", "unknown"),
                "source_name": item.get("source", {}).get("name", "unknown")
            }
            
            results.append({
                "title": title,
                "content": content,
                "timestamp": timestamp,
                "url": url,
                "metadata": metadata
            })
        
        return results

    async def _parse_reddit_news(self, data: Dict, source_name: str) -> List[Dict]:
        """Parse Reddit JSON format."""
        items = data.get("data", {}).get("children", [])
        results = []
        
        for item in items:
            post_data = item.get("data", {})
            title = post_data.get("title", "")
            content = post_data.get("selftext", title)
            timestamp = str(post_data.get("created_utc", ""))
            url = f"https://reddit.com{post_data.get('permalink', '')}"
            
            metadata = {
                "source": source_name,
                "source_api": "reddit_json",
                "subreddit": post_data.get("subreddit", "bitcoin"),
                "score": post_data.get("score", 0),
                "comments": post_data.get("num_comments", 0)
            }
            
            results.append({
                "title": title,
                "content": content,
                "timestamp": timestamp,
                "url": url,
                "metadata": metadata
            })
        
        return results

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
                    if "coindesk" in feed_url:
                        source = "coindesk"
                    elif "cointelegraph" in feed_url:
                        source = "cointelegraph"
                    elif "decrypt" in feed_url:
                        source = "decrypt"
                    else:
                        source = "unknown"
                    
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
        - CoinMarketCap: 60 seconds  
        - CryptoCompare: 120 seconds (free tier news)
        """
        self.logger.info("Starting News Ingestion Service")
        
        rss_counter = 0
        cmc_counter = 0
        cryptocompare_counter = 0
        
        while True:
            try:
                # RSS feeds every 30 seconds
                if rss_counter % 30 == 0:
                    rss_news = await self.fetch_rss_news()
                    self.logger.info(f"RSS: Processed {len(rss_news)} items")
                
                # CoinMarketCap every 60 seconds
                if cmc_counter % 60 == 0:
                    cmc_data = await self.fetch_coinmarketcap_data()
                    self.logger.info(f"CoinMarketCap: Processed {len(cmc_data)} data items")
                
                # Free APIs every 120 seconds (multi-source fallback)
                if cryptocompare_counter % 120 == 0:
                    free_news = await self.fetch_free_crypto_news_tier3()
                    self.logger.info(f"Free APIs: Processed {len(free_news)} items")
                
                # Increment counters
                rss_counter += 1
                cmc_counter += 1
                cryptocompare_counter += 1
                
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
