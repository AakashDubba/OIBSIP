"""Tests for the regex/NLP intent command dispatcher."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from src.core.dispatcher import CommandDispatcher
from src.core.email_service import EmailDraft, EmailService
from src.core.reminder_service import Reminder, ReminderService
from src.services.news_service import NewsArticle, NewsResponse, NewsService
from src.services.search_service import SearchResponse, SearchService
from src.services.weather_service import WeatherInfo, WeatherResponse, WeatherService


@pytest.fixture
def mock_news_service() -> MagicMock:
    svc = MagicMock(spec=NewsService)
    svc.get_news.return_value = NewsResponse(
        success=True,
        articles=[NewsArticle("AI breakthrough", "Summary", "RSS", "http://news", "2026-10-07")],
        message="Fetched 1 article",
    )
    return svc


@pytest.fixture
def mock_weather_service() -> MagicMock:
    svc = MagicMock(spec=WeatherService)
    svc.get_weather.return_value = WeatherResponse(
        success=True,
        data=WeatherInfo("Tokyo", "Japan", 22.0, 71.6, "Clear sky", 55, 12.0),
        message="The weather in Tokyo is Clear sky at 22.0°C.",
    )
    return svc


@pytest.fixture
def mock_search_service() -> MagicMock:
    svc = MagicMock(spec=SearchService)
    svc.search.return_value = SearchResponse(
        success=True,
        query="Python",
        summary="Python is a programming language.",
        results=[],
    )
    return svc


@pytest.fixture
def dispatcher(
    mock_news_service: MagicMock,
    mock_weather_service: MagicMock,
    mock_search_service: MagicMock,
) -> CommandDispatcher:
    email_svc = EmailService()
    reminder_svc = ReminderService()
    return CommandDispatcher(
        news_service=mock_news_service,
        weather_service=mock_weather_service,
        search_service=mock_search_service,
        email_service=email_svc,
        reminder_service=reminder_svc,
    )


def test_greeting_intent(dispatcher: CommandDispatcher) -> None:
    res = dispatcher.dispatch("hello assistant")
    assert res.intent_name == "greeting"
    assert "Hello" in res.response_text
    assert not res.should_exit


def test_time_and_date_intents(dispatcher: CommandDispatcher) -> None:
    res_time = dispatcher.dispatch("what time is it")
    assert res_time.intent_name == "time"
    assert "current time is" in res_time.response_text

    res_date = dispatcher.dispatch("what is today's date")
    assert res_date.intent_name == "date"
    assert "Today is" in res_date.response_text


def test_news_intent_dispatch(dispatcher: CommandDispatcher, mock_news_service: MagicMock) -> None:
    res = dispatcher.dispatch("get news in technology")
    assert res.intent_name == "news"
    mock_news_service.get_news.assert_called_once_with(category="technology", limit=3)
    assert "AI breakthrough" in res.response_text


def test_weather_intent_dispatch(dispatcher: CommandDispatcher, mock_weather_service: MagicMock) -> None:
    res = dispatcher.dispatch("what is the weather in Tokyo")
    assert res.intent_name == "weather"
    mock_weather_service.get_weather.assert_called_once_with("Tokyo")
    assert "Tokyo" in res.response_text


def test_search_intent_dispatch(dispatcher: CommandDispatcher, mock_search_service: MagicMock) -> None:
    res = dispatcher.dispatch("search for Python")
    assert res.intent_name == "search"
    mock_search_service.search.assert_called_once_with("Python")
    assert "Python is a programming language" in res.response_text


def test_email_draft_and_confirm_lifecycle(dispatcher: CommandDispatcher) -> None:
    # 1. Create draft
    draft_res = dispatcher.dispatch("draft email to test@domain.com subject Meeting body See you at 3pm")
    assert draft_res.intent_name == "email_draft"
    assert "EMAIL DRAFT PREVIEW" in draft_res.response_text
    assert "test@domain.com" in draft_res.response_text
    draft_id = draft_res.metadata["draft_id"] if draft_res.metadata else ""
    assert draft_id

    # 2. Confirm without SMTP config should safely report configuration requirement
    confirm_res = dispatcher.dispatch(f"confirm draft {draft_id}")
    assert confirm_res.intent_name == "email_confirm"
    assert "SMTP credentials are not configured" in confirm_res.response_text


def test_email_draft_cancellation(dispatcher: CommandDispatcher) -> None:
    draft_res = dispatcher.dispatch("compose email to user@test.com subject Hello body World")
    draft_id = draft_res.metadata["draft_id"] if draft_res.metadata else ""
    
    cancel_res = dispatcher.dispatch(f"cancel draft {draft_id}")
    assert cancel_res.intent_name == "email_cancel"
    assert f"Draft {draft_id} has been discarded" in cancel_res.response_text


def test_reminder_dispatch(dispatcher: CommandDispatcher) -> None:
    res = dispatcher.dispatch("remind me in 30 seconds to take a break")
    assert res.intent_name == "reminder_schedule"
    assert "take a break" in res.response_text

    list_res = dispatcher.dispatch("list reminders")
    assert list_res.intent_name == "reminder_list"
    assert "take a break" in list_res.response_text


def test_exit_intent(dispatcher: CommandDispatcher) -> None:
    res = dispatcher.dispatch("exit")
    assert res.intent_name == "exit"
    assert res.should_exit is True


def test_unknown_fallback(dispatcher: CommandDispatcher) -> None:
    res = dispatcher.dispatch("gibberish nonexistent query 12345")
    assert res.intent_name == "unknown"
    assert "didn't recognize that command" in res.response_text
