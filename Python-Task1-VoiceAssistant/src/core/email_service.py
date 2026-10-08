"""Configurable email draft and sending service with two-stage confirmation.

Security Constraints:
- Default action ONLY creates a preview draft.
- Actual transmission requires explicit confirmation with the draft ID.
- NEVER logs sensitive credentials, SMTP passwords, tokens, or email bodies.
"""

from __future__ import annotations

import email.message
import logging
import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailDraft:
    """Preview draft requiring explicit confirmation prior to transmission."""
    draft_id: str
    recipient: str
    subject: str
    body: str
    created_at: str

    def format_preview(self) -> str:
        """User-facing preview string."""
        return (
            f"--- EMAIL DRAFT PREVIEW [ID: {self.draft_id}] ---\n"
            f"To:      {self.recipient}\n"
            f"Subject: {self.subject}\n"
            f"Body:    {self.body}\n"
            f"Status:  PENDING CONFIRMATION\n"
            f"------------------------------------------------"
        )


class EmailService:
    """Manages email drafting with mandatory confirmation before sending."""

    def __init__(
        self,
        smtp_server: str = "smtp.example.com",
        smtp_port: int = 587,
        sender_address: Optional[str] = None,
        sender_password: Optional[str] = None,
    ) -> None:
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_address = sender_address
        self._sender_password = sender_password  # Strictly masked from logs
        self._pending_drafts: Dict[str, EmailDraft] = {}

    def create_draft(self, recipient: str, subject: str, body: str) -> EmailDraft:
        """Create a pending draft and return its preview."""
        draft_id = str(uuid.uuid4())[:8]
        draft = EmailDraft(
            draft_id=draft_id,
            recipient=recipient.strip(),
            subject=subject.strip(),
            body=body.strip(),
            created_at=datetime.now().isoformat(),
        )
        self._pending_drafts[draft_id] = draft
        # Audit log creation without revealing message content or credentials
        logger.info("Created email draft [ID: %s] for recipient: %s", draft_id, draft.recipient)
        return draft

    def get_draft(self, draft_id: str) -> Optional[EmailDraft]:
        """Retrieve an existing pending draft."""
        return self._pending_drafts.get(draft_id)

    def cancel_draft(self, draft_id: str) -> bool:
        """Discard a pending draft."""
        if draft_id in self._pending_drafts:
            del self._pending_drafts[draft_id]
            logger.info("Cancelled email draft [ID: %s]", draft_id)
            return True
        return False

    def confirm_and_send(self, draft_id: str) -> tuple[bool, str]:
        """Explicitly confirm and transmit the specified draft.
        
        Requires that the draft exists. Discards draft after attempt.
        """
        draft = self._pending_drafts.get(draft_id)
        if not draft:
            return False, f"Draft ID '{draft_id}' not found or already processed."

        if not self.sender_address or not self._sender_password:
            # External SMTP is unconfigured; report cleanly without failing silently
            logger.warning("SMTP credentials not configured (EMAIL_SENDER_ADDRESS / EMAIL_SENDER_PASSWORD missing).")
            return (
                False,
                f"Cannot send email: SMTP credentials are not configured in environment. "
                f"Draft {draft_id} remains saved.",
            )

        # Attempt real SMTP transmission
        try:
            msg = email.message.EmailMessage()
            msg["From"] = self.sender_address
            msg["To"] = draft.recipient
            msg["Subject"] = draft.subject
            msg.set_content(draft.body)

            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10.0) as server:
                server.starttls()
                server.login(self.sender_address, self._sender_password)
                server.send_message(msg)

            # Successfully sent: clean up draft
            del self._pending_drafts[draft_id]
            logger.info("Successfully sent email [Draft ID: %s] to recipient", draft_id)
            return True, f"Email successfully sent to {draft.recipient}."

        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP authentication failed for sender address.")
            return False, "SMTP authentication failed. Please verify credentials."
        except Exception as exc:
            logger.error("Failed to send email via SMTP: %s", exc)
            return False, f"Failed to send email due to network/SMTP error: {exc}"
