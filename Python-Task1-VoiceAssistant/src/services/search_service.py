"""Web search and browser integration service.

Supports configurable search mechanism (DuckDuckGo instant answers or browser launch).
Gracefully handles offline states without fabricating search results.
"""

from __future__ import annotations

import logging
import urllib.parse
import webbrowser
from dataclasses import dataclass
from typing import Optional, List
import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    """Structured search snippet."""
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class SearchResponse:
    """Result of search execution."""
    success: bool
    query: str
    summary: str
    results: List[SearchResult]
    browser_opened: bool = False


class SearchService:
    """Configurable web search execution engine."""

    def __init__(
        self,
        provider: str = "duckduckgo",
        timeout: float = 5.0,
        enable_browser_fallback: bool = True,
    ) -> None:
        self.provider = provider.lower()
        self.timeout = timeout
        self.enable_browser_fallback = enable_browser_fallback

    def search(self, query: str, open_in_browser: bool = False) -> SearchResponse:
        """Execute a web search query.
        
        Attempts instant answer retrieval; can also launch browser if requested.
        """
        clean_query = query.strip()
        if not clean_query:
            return SearchResponse(
                success=False,
                query="",
                summary="Search query cannot be empty.",
                results=[],
            )

        if open_in_browser:
            return self._open_browser_search(clean_query)

        if self.provider == "duckduckgo":
            return self._query_duckduckgo(clean_query)

        # Default fallback to browser
        return self._open_browser_search(clean_query)

    def _query_duckduckgo(self, query: str) -> SearchResponse:
        """Query DuckDuckGo Instant Answer API."""
        encoded = urllib.parse.quote_plus(query)
        api_url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        try:
            resp = requests.get(
                api_url,
                headers={"User-Agent": "NewsWorldVoiceAssistant/1.0"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            abstract = data.get("AbstractText", "").strip()
            heading = data.get("Heading", query)
            abstract_url = data.get("AbstractURL", "")

            results: List[SearchResult] = []
            if abstract:
                results.append(SearchResult(title=heading, url=abstract_url, snippet=abstract))
                return SearchResponse(
                    success=True,
                    query=query,
                    summary=abstract,
                    results=results,
                )

            # Check related topics
            related = data.get("RelatedTopics", [])
            for item in related[:3]:
                if isinstance(item, dict) and "Text" in item:
                    snippet = item.get("Text", "")
                    url = item.get("FirstURL", "")
                    results.append(SearchResult(title=snippet[:40] + "...", url=url, snippet=snippet))

            if results:
                summary_text = results[0].snippet
                return SearchResponse(
                    success=True,
                    query=query,
                    summary=summary_text,
                    results=results,
                )

            # No instant answer found, open in browser if fallback enabled
            if self.enable_browser_fallback:
                return self._open_browser_search(query)

            return SearchResponse(
                success=False,
                query=query,
                summary=f"No direct search summary found for '{query}'.",
                results=[],
            )

        except requests.Timeout:
            logger.warning("Search query timed out for: %s", query)
            if self.enable_browser_fallback:
                return self._open_browser_search(query)
            return SearchResponse(
                success=False,
                query=query,
                summary="Search service timed out.",
                results=[],
            )
        except requests.RequestException as exc:
            logger.warning("Network error querying search provider: %s", exc)
            if self.enable_browser_fallback:
                return self._open_browser_search(query)
            return SearchResponse(
                success=False,
                query=query,
                summary=f"Search service error: {exc}",
                results=[],
            )
        except Exception as exc:
            logger.error("Unexpected search service error: %s", exc)
            return SearchResponse(
                success=False,
                query=query,
                summary=f"External search service unavailable: {exc}",
                results=[],
            )

    def _open_browser_search(self, query: str) -> SearchResponse:
        """Launch web browser with Google/DuckDuckGo search URL."""
        encoded = urllib.parse.quote_plus(query)
        target_url = f"https://www.google.com/search?q={encoded}"
        try:
            opened = webbrowser.open(target_url, new=2)
            if opened:
                return SearchResponse(
                    success=True,
                    query=query,
                    summary=f"Opened search for '{query}' in your default web browser.",
                    results=[SearchResult(title="Web Search", url=target_url, snippet=query)],
                    browser_opened=True,
                )
        except Exception as exc:
            logger.warning("Failed to open web browser: %s", exc)

        return SearchResponse(
            success=False,
            query=query,
            summary=f"Unable to launch web browser for search query '{query}'.",
            results=[],
            browser_opened=False,
        )
