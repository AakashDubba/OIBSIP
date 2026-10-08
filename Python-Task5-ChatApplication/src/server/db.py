"""SQLite Database and Cryptographic Security Manager.

Security Specifications:
- Passwords hashed using PBKDF2-HMAC-SHA256 with 100,000 iterations.
- Cryptographically secure 16-byte random salt generated per user via os.urandom.
- Plaintext passwords and salts are NEVER logged.
- Full audit logging for authentication events, room transitions, and message dispatch.
- Persistent message history with history replay.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

PBKDF2_ITERATIONS = 100_000
SALT_BYTES = 16


def hash_password(password: str, salt: bytes) -> str:
    """Derive hexadecimal PBKDF2-HMAC-SHA256 hash using salt."""
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return key.hex()


def verify_password(password: str, salt_hex: str, stored_hash_hex: str) -> bool:
    """Verify password against stored salt and hash in constant time."""
    try:
        salt = bytes.fromhex(salt_hex)
        candidate_hash = hash_password(password, salt)
        # Constant-time comparison to prevent timing side-channel attacks
        return hashlib.sha256(candidate_hash.encode()).digest() == hashlib.sha256(stored_hash_hex.encode()).digest()
    except Exception as exc:
        logger.error("Error during password hash verification: %s", exc)
        return False


class DatabaseManager:
    """Thread-safe SQLite database manager for authentication and audit trails."""

    def __init__(self, db_path: str | Path = "clinical_chat.db") -> None:
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create database schema if not already initialized."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            # 1. Users Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    salt_hex TEXT NOT NULL,
                    password_hash_hex TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # 2. Messages & Room History Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    packet_id TEXT UNIQUE NOT NULL,
                    room TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            # 3. Security Audit Log Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    username TEXT NOT NULL,
                    details TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()
            logger.info("Initialized ClinicFlow database schema at %s", self.db_path)

    # ---------------- AUTHENTICATION OPERATIONS ----------------

    def register_user(self, username: str, password: str, role: str) -> Tuple[bool, str]:
        """Register a new user with cryptographic salt and PBKDF2 hash."""
        clean_user = username.strip()
        if not clean_user or len(clean_user) < 3:
            return False, "Username must be at least 3 characters."
        if not password or len(password) < 6:
            return False, "Password must be at least 6 characters."

        salt = os.urandom(SALT_BYTES)
        salt_hex = salt.hex()
        hash_hex = hash_password(password, salt)
        created_at = datetime.now().isoformat()

        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (username, salt_hex, password_hash_hex, role, created_at) VALUES (?, ?, ?, ?, ?)",
                    (clean_user, salt_hex, hash_hex, role.upper(), created_at),
                )
                conn.commit()
                self._record_audit_event(conn, "USER_REGISTERED", clean_user, f"Role: {role.upper()}")
                logger.info("Registered user '%s' with role %s", clean_user, role.upper())
                return True, "User registered successfully."
            except sqlite3.IntegrityError:
                return False, f"Username '{clean_user}' is already registered."

    def authenticate_user(self, username: str, password: str) -> Tuple[bool, Optional[str], str]:
        """Authenticate user credentials. Returns (success, role, message)."""
        clean_user = username.strip()
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT salt_hex, password_hash_hex, role FROM users WHERE username = ?",
                (clean_user,),
            )
            row = cursor.fetchone()
            if not row:
                self._record_audit_event(conn, "AUTH_FAILED_USER_NOT_FOUND", clean_user, "Unknown username")
                return False, None, "Invalid username or password."

            salt_hex = row["salt_hex"]
            stored_hash = row["password_hash_hex"]
            role = row["role"]

            if verify_password(password, salt_hex, stored_hash):
                self._record_audit_event(conn, "AUTH_SUCCESS", clean_user, f"Authenticated as {role}")
                logger.info("User '%s' authenticated successfully as %s", clean_user, role)
                return True, role, "Authentication successful."

            self._record_audit_event(conn, "AUTH_FAILED_WRONG_PASSWORD", clean_user, "Incorrect password attempt")
            return False, None, "Invalid username or password."

    # ---------------- MESSAGE AUDIT & HISTORY REPLAY ----------------

    def store_message(
        self,
        packet_id: str,
        room: str,
        sender: str,
        role: str,
        message: str,
        timestamp: str,
    ) -> bool:
        """Store clinical chat message to persistent SQLite store."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO messages (packet_id, room, sender, role, message, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (packet_id, room, sender, role.upper(), message, timestamp),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                logger.warning("Duplicate message packet_id %s ignored", packet_id)
                return False

    def get_room_history(self, room: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve historical messages for replay when client joins room."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT packet_id, room, sender, role, message, timestamp
                FROM messages
                WHERE room = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (room, limit),
            )
            rows = cursor.fetchall()
            return [
                {
                    "packet_id": r["packet_id"],
                    "room": r["room"],
                    "sender": r["sender"],
                    "role": r["role"],
                    "message": r["message"],
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]

    # ---------------- AUDIT LOGGING ----------------

    def _record_audit_event(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        username: str,
        details: str,
    ) -> None:
        """Internal audit trail writer (never logs passwords or secrets)."""
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO audit_logs (event_type, username, details, timestamp) VALUES (?, ?, ?, ?)",
            (event_type, username, details, datetime.now().isoformat()),
        )
        conn.commit()

    def get_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Query audit log entries."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]
