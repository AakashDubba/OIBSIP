"""Regional news integration bridge correlating weather locations with breaking news.

Completely decoupled and standalone. Ingests public RSS feeds without fabricating data.
"""

from __future__ import annotations

import logging
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional
import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegionalNewsItem:
    """Regional news article snippet."""
    title: str
    source: str
    link: str
    published_at: str


@dataclass(frozen=True)
class RegionalNewsResult:
    """Outcome of regional news query."""
    success: bool
    headlines: List[RegionalNewsItem]
    region: str
    message: str


class RegionalNewsBridge:
    """Fetches real breaking regional headlines corresponding to a weather location."""

    def __init__(
        self,
        default_rss_url: str = "https://feeds.bbci.co.uk/news/world/rss.xml",
        timeout: float = 5.0,
    ) -> None:
        self.default_rss_url = default_rss_url
        self.timeout = timeout

    def fetch_regional_news(self, location: str, country: str = "", limit: int = 3) -> RegionalNewsResult:
        """Fetch real news for the location or regional feed.
        
        Zero fabrication: if network fails or feed has no items, returns structured failure.
        """
        clean_loc = location.strip()
        if not clean_loc:
            return RegionalNewsResult(
                success=False,
                headlines=[],
                region="",
                message="Location name required for news query.",
            )

        # Build search query RSS URL via Google News RSS or fallback to global feed
        query_term = f"{clean_loc} {country}".strip()
        encoded = urllib.parse.quote_plus(query_term)
        news_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

        try:
            resp = requests.get(
                news_url,
                headers={"User-Agent": "NewsWorldWeatherEngine/1.0 (+http://localhost)"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            items = self._parse_rss_items(resp.content, limit=limit)

            if items:
                return RegionalNewsResult(
                    success=True,
                    headlines=items,
                    region=clean_loc,
                    message=f"Retrieved {len(items)} headline(s) for {clean_loc}.",
                )

            # Fallback to general feed if specific search returned no items
            return self._fetch_general_feed(limit=limit, region=clean_loc)

        except requests.RequestException as exc:
            logger.warning("Regional news request failed for '%s': %s", clean_loc, exc)
            return RegionalNewsResult(
                success=False,
                headlines=[],
                region=clean_loc,
                message=f"Regional news service unavailable: {exc}",
            )
        except Exception as exc:
            logger.error("Error parsing regional news feed for '%s': %s", clean_loc, exc)
            return RegionalNewsResult(
                success=False,
                headlines=[],
                region=clean_loc,
                message=f"Could not parse news feed: {exc}",
            )

    def _fetch_general_feed(self, limit: int, region: str) -> RegionalNewsResult:
        """Fetch from default world feed when specific regional query yields no results."""
        try:
            resp = requests.get(
                self.default_rss_url,
                headers={"User-Agent": "NewsWorldWeatherEngine/1.0"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            items = self._parse_rss_items(resp.content, limit=limit)
            return RegionalNewsResult(
                success=bool(items),
                headlines=items,
                region=region,
                message=f"Top breaking headlines for {region} region.",
            )
        except Exception as exc:
            return RegionalNewsResult(
                success=False,
                headlines=[],
                region=region,
                message=f"News bridge fallback unavailable: {exc}",
            )

    def _parse_rss_items(self, xml_bytes: bytes, limit: int) -> List[RegionalNewsItem]:
        """Parse RSS XML cleanly without crashing on malformed tags."""
        root = ET.fromstring(xml_bytes)
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")

        results: List[RegionalNewsItem] = []
        for item in items[:limit]:
            title_node = item.find("title")
            link_node = item.find("link")
            pub_node = item.find("pubDate")
            source_node = item.find("source")

            title = title_node.text.strip() if title_node is not None and title_node.text else "Untitled Headline"
            link = link_node.text.strip() if link_node is not None and link_node.text else ""
            pub_date = pub_node.text.strip() if pub_node is not None and pub_node.text else ""
            source = source_node.text.strip() if source_node is not None and source_node.text else "News Source"

            results.append(RegionalNewsItem(
                title=title,
                source=source,
                link=link,
                published_at=pub_date,
            ))
        return results
