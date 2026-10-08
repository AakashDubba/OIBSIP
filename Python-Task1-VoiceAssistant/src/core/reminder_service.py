"""Thread-safe reminders and alarm scheduling service.

Allows users to schedule reminders with seconds/minutes delay.
Executes non-blocking background timers with callback or speech notification.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Reminder:
    """Scheduled reminder model."""
    reminder_id: str
    message: str
    trigger_time: datetime
    created_at: datetime


class ReminderService:
    """Manages scheduled alarms and reminders in background timer threads."""

    def __init__(self, on_trigger: Optional[Callable[[Reminder], None]] = None) -> None:
        self.on_trigger = on_trigger or self._default_trigger_handler
        self._reminders: Dict[str, Reminder] = {}
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _default_trigger_handler(self, reminder: Reminder) -> None:
        logger.info("REMINDER ALERT: %s (Scheduled at: %s)", reminder.message, reminder.trigger_time)

    def schedule_reminder(self, message: str, delay_seconds: float) -> Reminder:
        """Schedule a reminder to trigger after delay_seconds."""
        reminder_id = str(uuid.uuid4())[:6]
        now = datetime.now()
        trigger_time = now + timedelta(seconds=max(0.0, delay_seconds))

        reminder = Reminder(
            reminder_id=reminder_id,
            message=message.strip(),
            trigger_time=trigger_time,
            created_at=now,
        )

        with self._lock:
            self._reminders[reminder_id] = reminder
            timer = threading.Timer(delay_seconds, self._on_timer_fired, args=[reminder_id])
            timer.daemon = True
            self._timers[reminder_id] = timer
            timer.start()

        logger.info("Scheduled reminder [%s] '%s' in %.1fs", reminder_id, reminder.message, delay_seconds)
        return reminder

    def _on_timer_fired(self, reminder_id: str) -> None:
        """Invoked when timer expires."""
        reminder = None
        with self._lock:
            reminder = self._reminders.pop(reminder_id, None)
            self._timers.pop(reminder_id, None)

        if reminder is not None and self.on_trigger is not None:
            try:
                self.on_trigger(reminder)
            except Exception as exc:
                logger.error("Error executing reminder trigger callback: %s", exc)

    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel an active scheduled reminder."""
        with self._lock:
            timer = self._timers.pop(reminder_id, None)
            if timer:
                timer.cancel()
            removed = self._reminders.pop(reminder_id, None)
            return removed is not None

    def list_active_reminders(self) -> List[Reminder]:
        """Return list of active pending reminders."""
        with self._lock:
            return list(self._reminders.values())

    def shutdown(self) -> None:
        """Cancel all pending timers upon shutdown."""
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
            self._reminders.clear()
        logger.debug("ReminderService shutdown complete.")
