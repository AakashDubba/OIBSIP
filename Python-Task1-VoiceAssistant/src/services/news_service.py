"""News ingestion service supporting live RSS feeds and NewsAPI with thread-safe TTL caching.

Design Principles:
- Resilient network calls with timeouts.
- In-memory TTL caching with thread-safety.
- Absolute zero fabrication: if external feeds fail, cleanly reports unavailability.
"""

from __future__ import annotations

import logging
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Dict
import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NewsArticle:
    """Structured representation of a single news item."""
    title: str
    description: str
    source: str
    link: str
    published_at: str


@dataclass(frozen=True)
class NewsResponse:
    """Result of a news service query."""
    success: bool
    articles: List[NewsArticle]
    message: str
    cached: bool = False


@dataclass
class _CacheEntry:
    timestamp: float
    articles: List[NewsArticle]


class NewsService:
    """Ingests live news feeds with in-memory TTL caching and graceful fallbacks."""

    # Categorical RSS feed mappings for common topics
    CATEGORY_FEEDS: Dict[str, str] = {
        "world": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "business": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "science": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "general": "https://feeds.bbci.co.uk/news/rss.xml",
    }

    def __init__(
        self,
        default_rss_url: Optional[str] = None,
        api_key: Optional[str] = None,
        ttl_seconds: int = 300,
        request_timeout: float = 6.0,
    ) -> None:
        self.default_rss_url = default_rss_url or self.CATEGORY_FEEDS["general"]
        self.api_key = api_key
        self.ttl_seconds = ttl_seconds
        self.request_timeout = request_timeout

        self._cache: Dict[str, _CacheEntry] = {}
        self._cache_lock = threading.Lock()

    def get_news(
        self,
        category: Optional[str] = None,
        limit: int = 5,
        force_refresh: bool = False,
    ) -> NewsResponse:
        """Fetch latest news articles for a category or default feed.
        
        Uses in-memory cache if within TTL and force_refresh is False.
        """
        category_key = (category or "general").strip().lower()
        rss_url = self.CATEGORY_FEEDS.get(category_key, self.default_rss_url)

        # Check Cache
        if not force_refresh:
            with self._cache_lock:
                entry = self._cache.get(category_key)
                if entry and (time.time() - entry.timestamp < self.ttl_seconds):
                    logger.debug("Serving news for '%s' from cache (age: %.1fs)", category_key, time.time() - entry.timestamp)
                    return NewsResponse(
                        success=True,
                        articles=entry.articles[:limit],
                        message=f"Retrieved {len(entry.articles[:limit])} cached headline(s) for '{category_key}'.",
                        cached=True,
                    )

        # Attempt Live Ingestion via RSS
        try:
            articles = self._fetch_from_rss(rss_url)
            if not articles:
                return NewsResponse(
                    success=False,
                    articles=[],
                    message=f"No headlines found at news feed for category '{category_key}'.",
                    cached=False,
                )

            # Update Cache
            with self._cache_lock:
                self._cache[category_key] = _CacheEntry(
                    timestamp=time.time(),
                    articles=articles,
                )

            return NewsResponse(
                success=True,
                articles=articles[:limit],
                message=f"Fetched {len(articles[:limit])} live headline(s) for '{category_key}'.",
                cached=False,
            )

        except requests.Timeout:
            logger.warning("News service request timed out after %ss for %s", self.request_timeout, rss_url)
            return self._fallback_from_cache(category_key, "External news feed timed out.")
        except requests.RequestException as exc:
            logger.warning("Network error fetching news: %s", exc)
            return self._fallback_from_cache(category_key, f"Network error contacting news feed: {exc}")
        except ET.ParseError as exc:
            logger.error("Failed to parse RSS XML response: %s", exc)
            return NewsResponse(
                success=False,
                articles=[],
                message="Received invalid or unparseable feed data from news provider.",
                cached=False,
            )
        except Exception as exc:
            logger.error("Unexpected error in news service: %s", exc)
            return NewsResponse(
                success=False,
                articles=[],
                message=f"External news service is currently unavailable: {exc}",
                cached=False,
            )

    def _fetch_from_rss(self, url: str) -> List[NewsArticle]:
        """Fetch and parse RSS XML into typed NewsArticle models."""
        headers = {"User-Agent": "NewsWorldVoiceAssistant/1.0 (+http://localhost)"}
        response = requests.get(url, headers=headers, timeout=self.request_timeout)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        articles: List[NewsArticle] = []

        # Parse standard RSS 2.0 channel items
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")

        for item in items:
            title_elem = item.find("title")
            desc_elem = item.find("description")
            link_elem = item.find("link")
            pub_elem = item.find("pubDate")

            title = title_elem.text.strip() if title_elem is not None and title_elem.text else "Untitled"
            desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
            link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            pub_date = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""

            # Strip HTML tags from description if present
            clean_desc = ET.fromstring(f"<span>{desc}</span>").text if "<" not in desc else desc

            articles.append(NewsArticle(
                title=title,
                description=clean_desc or "",
                source="RSS Feed",
                link=link,
                published_at=pub_date,
            ))

        return articles

    def _fallback_from_cache(self, category_key: str, reason: str) -> NewsResponse:
        """Attempt to serve stale cache during outage if available, otherwise fail cleanly."""
        with self._cache_lock:
            entry = self._cache.get(category_key)
            if entry and entry.articles:
                logger.info("Serving stale cached news during network outage for '%s'", category_key)
                return NewsResponse(
                    success=True,
                    articles=entry.articles,
                    message=f"{reason} Serving previously cached headlines.",
                    cached=True,
                )
        return NewsResponse(
            success=False,
            articles=[],
            message=f"{reason} News service is currently unavailable.",
            cached=False,
        )

    def clear_cache(self) -> None:
        """Clear the in-memory news cache."""
        with self._cache_lock:
            self._cache.clear()
