"""Tests for cryptographic security, PBKDF2 hashing, and SQLite audit logging."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from src.server.db import DatabaseManager, hash_password, verify_password


def test_pbkdf2_per_user_salt_isolation() -> None:
    password = "SecureClinicalPass123!"

    salt1 = os.urandom(16)
    salt2 = os.urandom(16)

    hash1 = hash_password(password, salt1)
    hash2 = hash_password(password, salt2)

    # Identical password with distinct cryptographic salts must yield completely different hashes
    assert hash1 != hash2
    assert len(hash1) == 64  # SHA-256 hex digest length
    assert len(hash2) == 64

    # Verification must succeed with correct salt
    assert verify_password(password, salt1.hex(), hash1) is True
    assert verify_password(password, salt2.hex(), hash2) is True
    # Verification must fail with wrong password
    assert verify_password("WrongPass", salt1.hex(), hash1) is False


def test_database_user_auth_lifecycle(tmp_path: Path) -> None:
    db_file = tmp_path / "test_auth.db"
    db = DatabaseManager(db_file)

    # 1. Register user
    ok, msg = db.register_user("dr_house", "Diagnosis123!", "DOCTOR")
    assert ok is True
    assert "registered successfully" in msg.lower()

    # 2. Duplicate registration rejected
    dup_ok, dup_msg = db.register_user("dr_house", "AnotherPass", "DOCTOR")
    assert dup_ok is False
    assert "already registered" in dup_msg.lower()

    # 3. Successful authentication
    auth_ok, role, auth_msg = db.authenticate_user("dr_house", "Diagnosis123!")
    assert auth_ok is True
    assert role == "DOCTOR"

    # 4. Failed authentication (wrong password)
    fail_ok, _, _ = db.authenticate_user("dr_house", "WrongPassword")
    assert fail_ok is False

    # 5. Failed authentication (unknown username)
    unknown_ok, _, _ = db.authenticate_user("nonexistent_user", "AnyPassword")
    assert unknown_ok is False


def test_database_message_history_and_replay(tmp_path: Path) -> None:
    db_file = tmp_path / "test_history.db"
    db = DatabaseManager(db_file)

    # Store messages across two different rooms
    db.store_message("p1", "#triage", "nurse_ratched", "NURSE", "Patient triage admission", "2026-10-08T01:00")
    db.store_message("p2", "#triage", "dr_smith", "DOCTOR", "Ordered blood panel", "2026-10-08T01:02")
    db.store_message("p3", "#general", "nurse_betty", "NURSE", "Cafeteria lunch break", "2026-10-08T01:05")

    # Replay triage history
    triage_history = db.get_room_history("#triage")
    assert len(triage_history) == 2
    assert triage_history[0]["message"] == "Patient triage admission"
    assert triage_history[1]["message"] == "Ordered blood panel"

    # Replay general history
    gen_history = db.get_room_history("#general")
    assert len(gen_history) == 1
    assert gen_history[0]["message"] == "Cafeteria lunch break"


def test_database_audit_logs(tmp_path: Path) -> None:
    db_file = tmp_path / "test_audit.db"
    db = DatabaseManager(db_file)

    db.register_user("admin_user", "AdminSecret123!", "ADMIN")
    db.authenticate_user("admin_user", "AdminSecret123!")
    db.authenticate_user("admin_user", "WrongAttempt")

    logs = db.get_audit_logs(limit=10)
    assert len(logs) >= 3

    event_types = [entry["event_type"] for entry in logs]
    assert "USER_REGISTERED" in event_types
    assert "AUTH_SUCCESS" in event_types
    assert "AUTH_FAILED_WRONG_PASSWORD" in event_types
