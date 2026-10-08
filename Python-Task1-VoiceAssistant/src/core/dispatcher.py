"""Intent dispatcher mapping user voice/text utterances to executable actions.

Features:
- Regex and pattern-based natural language intent classification.
- Support for structured parameters (e.g., location, query, email fields, timer durations).
- Clear, extensible handler architecture.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Pattern, Tuple

from src.core.email_service import EmailService
from src.core.reminder_service import ReminderService
from src.services.news_service import NewsService
from src.services.search_service import SearchService
from src.services.weather_service import WeatherService

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """Outcome of dispatching an utterance."""
    intent_name: str
    response_text: str
    should_exit: bool = False
    metadata: Optional[Dict[str, str]] = None


HandlerFunc = Callable[[str, re.Match], IntentResult]


@dataclass
class IntentRule:
    """A pattern matching rule associated with a handler."""
    name: str
    patterns: List[Pattern[str]]
    handler: HandlerFunc
    description: str


class CommandDispatcher:
    """Dispatches natural language utterances to corresponding service handlers."""

    def __init__(
        self,
        news_service: Optional[NewsService] = None,
        weather_service: Optional[WeatherService] = None,
        search_service: Optional[SearchService] = None,
        email_service: Optional[EmailService] = None,
        reminder_service: Optional[ReminderService] = None,
    ) -> None:
        self.news_service = news_service or NewsService()
        self.weather_service = weather_service or WeatherService()
        self.search_service = search_service or SearchService()
        self.email_service = email_service or EmailService()
        self.reminder_service = reminder_service or ReminderService()

        self._rules: List[IntentRule] = []
        self._register_default_rules()

    def _register_rule(self, name: str, patterns: List[str], handler: HandlerFunc, desc: str) -> None:
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        self._rules.append(IntentRule(name=name, patterns=compiled, handler=handler, description=desc))

    def _register_default_rules(self) -> None:
        # Exit
        self._register_rule(
            name="exit",
            patterns=[
                r"^(exit|quit|bye|goodbye|stop|shutdown)$",
                r"^(please )?(exit|quit|shut down) (the )?(assistant|system)?$",
            ],
            handler=self._handle_exit,
            desc="Exit the voice assistant",
        )

        # Help / Capabilities
        self._register_rule(
            name="help",
            patterns=[
                r"^(help|what can you do|capabilities|commands)$",
                r"^who are you$",
            ],
            handler=self._handle_help,
            desc="Display available capabilities",
        )

        # Greetings
        self._register_rule(
            name="greeting",
            patterns=[
                r"^(hello|hi|hey|greetings|good morning|good evening|good afternoon)( assistant)?$",
            ],
            handler=self._handle_greeting,
            desc="Greet the assistant",
        )

        # Date & Time
        self._register_rule(
            name="time",
            patterns=[
                r"what time is it",
                r"current time",
                r"tell me the time",
            ],
            handler=self._handle_time,
            desc="Tell the current time",
        )
        self._register_rule(
            name="date",
            patterns=[
                r"what('s| is) (today's |the )?date",
                r"what day is (it|today)",
                r"today's date",
            ],
            handler=self._handle_date,
            desc="Tell the current date",
        )

        # News
        self._register_rule(
            name="news",
            patterns=[
                r"(?:tell me|get|read|show)?\s*(?:the\s+)?(?:latest\s+)?news(?:\s+(?:in|about|on)\s+(?P<category>\w+))?",
                r"headlines(?:\s+(?:in|about)\s+(?P<cat_alt>\w+))?",
            ],
            handler=self._handle_news,
            desc="Get breaking news and headlines by topic",
        )

        # Weather
        self._register_rule(
            name="weather",
            patterns=[
                r"weather in (?P<city>[a-zA-Z\s,]+)",
                r"what('s| is) the weather (?:like )?(?:in |for )?(?P<city_alt>[a-zA-Z\s,]+)?",
            ],
            handler=self._handle_weather,
            desc="Query current weather conditions",
        )

        # Web Search
        self._register_rule(
            name="search",
            patterns=[
                r"(?:search for|google|look up|search)\s+(?P<query>.+)",
                r"who is (?P<who_query>.+)",
                r"what is (?P<what_query>(?!the time|the date|the weather).+)",
            ],
            handler=self._handle_search,
            desc="Perform a web search",
        )

        # Email Drafting
        self._register_rule(
            name="email_draft",
            patterns=[
                r"(?:draft|compose|send)\s+email\s+to\s+(?P<to>[^\s]+@[^\s]+|\S+)\s+(?:with\s+)?subject\s+(?P<subject>.+?)\s+(?:and\s+)?body\s+(?P<body>.+)",
            ],
            handler=self._handle_email_draft,
            desc="Draft a safe email preview",
        )

        # Email Confirmation & Cancellation
        self._register_rule(
            name="email_confirm",
            patterns=[
                r"(?:confirm|approve|send)\s+(?:email\s+)?draft\s+(?P<id>[a-zA-Z0-9]+)",
                r"send draft\s+(?P<id_alt>[a-zA-Z0-9]+)",
            ],
            handler=self._handle_email_confirm,
            desc="Explicitly confirm and transmit an email draft",
        )
        self._register_rule(
            name="email_cancel",
            patterns=[
                r"(?:cancel|discard|delete)\s+(?:email\s+)?draft\s+(?P<id>[a-zA-Z0-9]+)",
            ],
            handler=self._handle_email_cancel,
            desc="Discard a pending email draft",
        )

        # Reminders & Alarms
        self._register_rule(
            name="reminder_schedule",
            patterns=[
                r"remind me in (?P<count>\d+)\s*(?P<unit>seconds?|secs?|minutes?|mins?)\s*(?:to\s+)?(?P<msg>.+)",
                r"set (?:a )?(?:timer|alarm) for (?P<count_alt>\d+)\s*(?P<unit_alt>seconds?|secs?|minutes?|mins?)(?:\s*(?:to|for)\s*(?P<msg_alt>.+))?",
            ],
            handler=self._handle_reminder_schedule,
            desc="Schedule a reminder timer",
        )
        self._register_rule(
            name="reminder_list",
            patterns=[
                r"list (?:all )?reminders",
                r"show (?:my )?reminders",
            ],
            handler=self._handle_reminder_list,
            desc="List active scheduled reminders",
        )
        self._register_rule(
            name="reminder_cancel",
            patterns=[
                r"cancel reminder (?P<id>[a-zA-Z0-9]+)",
            ],
            handler=self._handle_reminder_cancel,
            desc="Cancel a scheduled reminder",
        )

    def dispatch(self, utterance: str) -> IntentResult:
        """Match an utterance against registered rules and execute the handler."""
        cleaned = utterance.strip()
        if not cleaned:
            return IntentResult(
                intent_name="empty",
                response_text="I didn't hear anything. Please speak or type a command.",
            )

        logger.debug("Dispatching utterance: '%s'", cleaned)
        for rule in self._rules:
            for pattern in rule.patterns:
                match = pattern.search(cleaned)
                if match:
                    logger.info("Matched intent '%s' on utterance: '%s'", rule.name, cleaned)
                    try:
                        return rule.handler(cleaned, match)
                    except Exception as exc:
                        logger.error("Error executing handler for intent '%s': %s", rule.name, exc)
                        return IntentResult(
                            intent_name=rule.name,
                            response_text=f"Encountered an internal error processing '{rule.name}': {exc}",
                        )

        # Fallback intent
        return IntentResult(
            intent_name="unknown",
            response_text=(
                "I didn't recognize that command. "
                "You can ask for news, weather, time, web search, email drafting, or reminders. "
                "Type 'help' for examples."
            ),
        )

    # ---------------- HANDLER IMPLEMENTATIONS ----------------

    def _handle_exit(self, utterance: str, match: re.Match) -> IntentResult:
        return IntentResult(
            intent_name="exit",
            response_text="Goodbye! Have a great day.",
            should_exit=True,
        )

    def _handle_help(self, utterance: str, match: re.Match) -> IntentResult:
        capabilities = [
            "NewsWorld AI Voice Assistant Commands:",
            "• 'time' or 'date' -> Current system time & date",
            "• 'news' or 'news in technology' -> Live RSS breaking news",
            "• 'weather in London' -> Real current weather conditions",
            "• 'search for quantum computing' -> Web search via DuckDuckGo / browser",
            "• 'draft email to user@domain.com subject Hello body How are you' -> Preview draft",
            "• 'confirm draft <ID>' -> Transmit draft (requires explicit confirmation)",
            "• 'remind me in 10 seconds to take a break' -> Background timer alert",
            "• 'list reminders' -> View scheduled reminders",
            "• 'exit' -> Quit assistant",
        ]
        return IntentResult(intent_name="help", response_text="\n".join(capabilities))

    def _handle_greeting(self, utterance: str, match: re.Match) -> IntentResult:
        return IntentResult(
            intent_name="greeting",
            response_text="Hello! I am your NewsWorld AI Assistant. How can I help you today?",
        )

    def _handle_time(self, utterance: str, match: re.Match) -> IntentResult:
        now_str = datetime.now().strftime("%I:%M %p")
        return IntentResult(intent_name="time", response_text=f"The current time is {now_str}.")

    def _handle_date(self, utterance: str, match: re.Match) -> IntentResult:
        date_str = datetime.now().strftime("%A, %B %d, %Y")
        return IntentResult(intent_name="date", response_text=f"Today is {date_str}.")

    def _handle_news(self, utterance: str, match: re.Match) -> IntentResult:
        category = match.groupdict().get("category") or match.groupdict().get("cat_alt")
        resp = self.news_service.get_news(category=category, limit=3)
        if not resp.success:
            return IntentResult(intent_name="news", response_text=resp.message)

        lines = [f"Here are the latest headlines in {category or 'world news'}:"]
        for idx, art in enumerate(resp.articles, 1):
            lines.append(f"{idx}. {art.title}")
        return IntentResult(intent_name="news", response_text="\n".join(lines))

    def _handle_weather(self, utterance: str, match: re.Match) -> IntentResult:
        city = match.groupdict().get("city") or match.groupdict().get("city_alt") or "London"
        city = city.strip()
        resp = self.weather_service.get_weather(city)
        return IntentResult(intent_name="weather", response_text=resp.message)

    def _handle_search(self, utterance: str, match: re.Match) -> IntentResult:
        query = (
            match.groupdict().get("query")
            or match.groupdict().get("who_query")
            or match.groupdict().get("what_query")
            or ""
        ).strip()
        resp = self.search_service.search(query)
        return IntentResult(intent_name="search", response_text=resp.summary)

    def _handle_email_draft(self, utterance: str, match: re.Match) -> IntentResult:
        to_addr = match.group("to")
        subject = match.group("subject")
        body = match.group("body")

        draft = self.email_service.create_draft(to_addr, subject, body)
        resp_text = (
            f"Draft created successfully!\n\n"
            f"{draft.format_preview()}\n\n"
            f"To transmit this email, confirm by saying or typing: 'confirm draft {draft.draft_id}'\n"
            f"To discard, use: 'cancel draft {draft.draft_id}'"
        )
        return IntentResult(intent_name="email_draft", response_text=resp_text, metadata={"draft_id": draft.draft_id})

    def _handle_email_confirm(self, utterance: str, match: re.Match) -> IntentResult:
        draft_id = match.groupdict().get("id") or match.groupdict().get("id_alt") or ""
        success, msg = self.email_service.confirm_and_send(draft_id)
        return IntentResult(intent_name="email_confirm", response_text=msg)

    def _handle_email_cancel(self, utterance: str, match: re.Match) -> IntentResult:
        draft_id = match.group("id")
        cancelled = self.email_service.cancel_draft(draft_id)
        msg = f"Draft {draft_id} has been discarded." if cancelled else f"Draft {draft_id} was not found."
        return IntentResult(intent_name="email_cancel", response_text=msg)

    def _handle_reminder_schedule(self, utterance: str, match: re.Match) -> IntentResult:
        count_str = match.groupdict().get("count") or match.groupdict().get("count_alt") or "10"
        unit_str = match.groupdict().get("unit") or match.groupdict().get("unit_alt") or "seconds"
        msg = match.groupdict().get("msg") or match.groupdict().get("msg_alt") or "Alert reminder"

        count = float(count_str)
        multiplier = 60.0 if "min" in unit_str.lower() else 1.0
        seconds = count * multiplier

        rem = self.reminder_service.schedule_reminder(msg, delay_seconds=seconds)
        return IntentResult(
            intent_name="reminder_schedule",
            response_text=f"Reminder set! I will alert you about '{rem.message}' in {int(count)} {unit_str} [ID: {rem.reminder_id}].",
            metadata={"reminder_id": rem.reminder_id},
        )

    def _handle_reminder_list(self, utterance: str, match: re.Match) -> IntentResult:
        active = self.reminder_service.list_active_reminders()
        if not active:
            return IntentResult(intent_name="reminder_list", response_text="You have no active reminders.")

        lines = ["Active Reminders:"]
        for r in active:
            lines.append(f"• [ID: {r.reminder_id}] '{r.message}' triggers at {r.trigger_time.strftime('%I:%M:%S %p')}")
        return IntentResult(intent_name="reminder_list", response_text="\n".join(lines))

    def _handle_reminder_cancel(self, utterance: str, match: re.Match) -> IntentResult:
        rem_id = match.group("id")
        cancelled = self.reminder_service.cancel_reminder(rem_id)
        msg = f"Reminder {rem_id} cancelled." if cancelled else f"Reminder {rem_id} not found."
        return IntentResult(intent_name="reminder_cancel", response_text=msg)
