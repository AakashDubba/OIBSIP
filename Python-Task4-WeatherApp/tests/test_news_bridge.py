"""Tests for RegionalNewsBridge integration adapter."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
import requests
from src.api.news_bridge import RegionalNewsBridge


MOCK_RSS_BYTES = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Regional Breaking News</title>
    <item>
      <title>Metropolitan Transit Announces Schedule Overhaul</title>
      <link>https://example.com/news/transit</link>
      <pubDate>Thu, 08 Oct 2026 08:30:00 GMT</pubDate>
      <source>Metro Herald</source>
    </item>
    <item>
      <title>Local Tech Summit Kicks Off Today</title>
      <link>https://example.com/news/tech</link>
      <pubDate>Thu, 08 Oct 2026 09:15:00 GMT</pubDate>
      <source>Tech Journal</source>
    </item>
  </channel>
</rss>
"""


def test_fetch_regional_news_success() -> None:
    bridge = RegionalNewsBridge()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = MOCK_RSS_BYTES
    mock_resp.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_resp):
        res = bridge.fetch_regional_news("Chicago", country="United States", limit=2)
        assert res.success is True
        assert len(res.headlines) == 2
        assert res.headlines[0].title == "Metropolitan Transit Announces Schedule Overhaul"
        assert res.headlines[0].source == "Metro Herald"
        assert res.headlines[1].title == "Local Tech Summit Kicks Off Today"


def test_fetch_regional_news_empty_location() -> None:
    bridge = RegionalNewsBridge()
    res = bridge.fetch_regional_news("   ")
    assert res.success is False
    assert len(res.headlines) == 0


def test_fetch_regional_news_network_failure() -> None:
    bridge = RegionalNewsBridge()

    with patch("requests.get", side_effect=requests.RequestException("DNS lookup failed")):
        res = bridge.fetch_regional_news("Seattle")
        assert res.success is False
        assert len(res.headlines) == 0
        assert "unavailable" in res.message.lower()
