"""Tests for NewsService live RSS ingestion and in-memory TTL caching."""

from __future__ import annotations

import time
from unittest.mock import patch, MagicMock
import requests
from src.services.news_service import NewsService


SAMPLE_RSS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BBC News - Technology</title>
    <item>
      <title>Quantum Computing Milestone Reached</title>
      <description>Scientists demonstrate 1000-qubit coherence.</description>
      <link>https://example.com/quantum</link>
      <pubDate>Wed, 07 Oct 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Renewable Energy Grid Update</title>
      <description>Solar installations double in 2026.</description>
      <link>https://example.com/energy</link>
      <pubDate>Wed, 07 Oct 2026 13:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_news_service_parsing() -> None:
    svc = NewsService(ttl_seconds=60)

    mock_resp = MagicMock()
    mock_resp.content = SAMPLE_RSS_XML
    mock_resp.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_resp):
        res = svc.get_news(category="technology")

        assert res.success is True
        assert res.cached is False
        assert len(res.articles) == 2
        assert res.articles[0].title == "Quantum Computing Milestone Reached"
        assert res.articles[1].title == "Renewable Energy Grid Update"


def test_news_service_ttl_caching() -> None:
    svc = NewsService(ttl_seconds=2)

    mock_resp = MagicMock()
    mock_resp.content = SAMPLE_RSS_XML
    mock_resp.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_resp) as mock_get:
        # 1. First call -> live fetch
        res1 = svc.get_news(category="technology")
        assert res1.success is True
        assert res1.cached is False
        assert mock_get.call_count == 1

        # 2. Immediate second call -> served from cache
        res2 = svc.get_news(category="technology")
        assert res2.success is True
        assert res2.cached is True
        assert mock_get.call_count == 1  # No additional network request

        # 3. Wait for TTL to expire
        time.sleep(2.1)
        res3 = svc.get_news(category="technology")
        assert res3.success is True
        assert res3.cached is False
        assert mock_get.call_count == 2  # Refetched after expiration


def test_news_service_graceful_error_handling() -> None:
    svc = NewsService(ttl_seconds=60)

    with patch("requests.get", side_effect=requests.Timeout("Connection timed out")):
        res = svc.get_news(category="general")
        assert res.success is False
        assert len(res.articles) == 0
        assert "timed out" in res.message.lower()
