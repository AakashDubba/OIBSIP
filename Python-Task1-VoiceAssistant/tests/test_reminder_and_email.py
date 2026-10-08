"""Tests for reminder scheduler and safe email draft/send workflow."""

from __future__ import annotations

import time
from unittest.mock import patch, MagicMock
from src.core.email_service import EmailService
from src.core.reminder_service import Reminder, ReminderService


def test_reminder_scheduler_trigger() -> None:
    triggered_alerts = []

    def on_alert(rem: Reminder) -> None:
        triggered_alerts.append(rem.message)

    svc = ReminderService(on_trigger=on_alert)

    # Schedule a rapid reminder for 0.2 seconds
    rem = svc.schedule_reminder("Test prompt", delay_seconds=0.2)
    assert len(svc.list_active_reminders()) == 1

    time.sleep(0.35)

    assert len(triggered_alerts) == 1
    assert triggered_alerts[0] == "Test prompt"
    assert len(svc.list_active_reminders()) == 0

    svc.shutdown()


def test_reminder_cancellation() -> None:
    svc = ReminderService()
    rem = svc.schedule_reminder("Cancelled reminder", delay_seconds=10.0)
    assert len(svc.list_active_reminders()) == 1

    cancelled = svc.cancel_reminder(rem.reminder_id)
    assert cancelled is True
    assert len(svc.list_active_reminders()) == 0

    svc.shutdown()


def test_email_draft_preview_and_protection() -> None:
    email_svc = EmailService()

    draft = email_svc.create_draft("alice@example.com", "Quarterly Report", "Attached is the report.")
    preview = draft.format_preview()

    assert "alice@example.com" in preview
    assert "Quarterly Report" in preview
    assert "PENDING CONFIRMATION" in preview
    assert draft.draft_id in preview

    # Verify sending without credentials safely fails and informs user
    ok, msg = email_svc.confirm_and_send(draft.draft_id)
    assert ok is False
    assert "SMTP credentials are not configured" in msg


def test_email_send_with_mocked_smtp() -> None:
    email_svc = EmailService(
        smtp_server="smtp.test.com",
        smtp_port=587,
        sender_address="bot@test.com",
        sender_password="secretpassword",
    )

    draft = email_svc.create_draft("recipient@test.com", "Subject", "Body content")

    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_instance

        ok, msg = email_svc.confirm_and_send(draft.draft_id)
        assert ok is True
        assert "successfully sent" in msg.lower()
        mock_instance.starttls.assert_called_once()
        mock_instance.login.assert_called_once_with("bot@test.com", "secretpassword")
        mock_instance.send_message.assert_called_once()

    # Draft should be consumed/removed
    assert email_svc.get_draft(draft.draft_id) is None
