"""Thread-safe ConnectionManager managing client sessions, rooms, and role authorization."""

from __future__ import annotations

import logging
import socket
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from src.protocol.schemas import ClinicalRoom, MessageType, Packet, Role
from src.protocol.serializer import send_framed_packet

logger = logging.getLogger(__name__)


@dataclass
class ClientSession:
    """Represents an active client TCP socket session."""
    session_id: str
    sock: socket.socket
    username: Optional[str] = None
    role: Optional[str] = None
    current_room: str = ClinicalRoom.GENERAL.value
    is_authenticated: bool = False
    connected_at: str = ""

    def info_dict(self) -> Dict[str, str]:
        return {
            "username": self.username or "Anonymous",
            "role": self.role or "GUEST",
            "room": self.current_room,
        }


class ConnectionManager:
    """Thread-safe manager for concurrent client sessions, rooms, and authorization."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # session_id -> ClientSession
        self._sessions: Dict[str, ClientSession] = {}
        # room_name -> Set[session_id]
        self._room_members: Dict[str, Set[str]] = {
            r.value: set() for r in ClinicalRoom
        }

    def register_client(self, session_id: str, client_sock: socket.socket) -> ClientSession:
        """Register newly connected client socket."""
        session = ClientSession(
            session_id=session_id,
            sock=client_sock,
            connected_at=datetime.now().isoformat(),
        )
        with self._lock:
            self._sessions[session_id] = session
            # Automatically place in #general by default
            self._room_members[ClinicalRoom.GENERAL.value].add(session_id)

        logger.info("Registered socket session [%s]. Total active sessions: %d", session_id, len(self._sessions))
        return session

    def authenticate_client(self, session_id: str, username: str, role: str) -> bool:
        """Mark session as authenticated with username and assigned role."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            session.username = username
            session.role = role.upper()
            session.is_authenticated = True
            logger.info("Session [%s] authenticated as user '%s' (%s)", session_id, username, role)
            return True

    def remove_client(self, session_id: str) -> Optional[ClientSession]:
        """Remove client from all rooms and active registry on disconnect."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if not session:
                return None

            for room_set in self._room_members.values():
                room_set.discard(session_id)

            logger.info("Removed session [%s] (user: %s). Remaining active: %d", session_id, session.username, len(self._sessions))
            return session

    def get_session(self, session_id: str) -> Optional[ClientSession]:
        """Retrieve session by ID."""
        with self._lock:
            return self._sessions.get(session_id)

    def switch_room(self, session_id: str, new_room: str) -> Tuple[bool, str]:
        """Move client session to new segregated clinical room with role verification."""
        if not ClinicalRoom.is_valid(new_room):
            return False, f"Room '{new_room}' does not exist. Valid rooms: {ClinicalRoom.all_rooms()}"

        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False, "Session not found."

            if not session.is_authenticated:
                return False, "Authentication required to switch clinical rooms."

            # Role-based Room Authorization Policies
            # #physician-consult: DOCTOR and ADMIN only (NURSES restricted unless elevated)
            if new_room == ClinicalRoom.PHYSICIAN_CONSULT.value and session.role not in (Role.DOCTOR.value, Role.ADMIN.value):
                logger.warning("Access denied: User '%s' (%s) attempted to enter %s", session.username, session.role, new_room)
                return False, f"Access restricted: {new_room} requires DOCTOR or ADMIN role."

            # Remove from prior room
            old_room = session.current_room
            self._room_members[old_room].discard(session_id)

            # Add to new room
            session.current_room = new_room
            self._room_members[new_room].add(session_id)

            logger.info("User '%s' switched room from %s to %s", session.username, old_room, new_room)
            return True, f"Successfully joined {new_room}."

    def broadcast_to_room(
        self,
        room: str,
        packet: Packet,
        exclude_session_id: Optional[str] = None,
    ) -> int:
        """Broadcast packet strictly to members in the designated clinical room."""
        recipients: List[socket.socket] = []

        with self._lock:
            session_ids = self._room_members.get(room, set()).copy()
            for s_id in session_ids:
                if exclude_session_id and s_id == exclude_session_id:
                    continue
                sess = self._sessions.get(s_id)
                if sess and sess.sock:
                    recipients.append(sess.sock)

        sent_count = 0
        for client_sock in recipients:
            if send_framed_packet(client_sock, packet):
                sent_count += 1

        return sent_count

    def send_to_session(self, session_id: str, packet: Packet) -> bool:
        """Send framed packet to a single specific client session."""
        sock = None
        with self._lock:
            sess = self._sessions.get(session_id)
            if sess:
                sock = sess.sock

        if sock:
            return send_framed_packet(sock, packet)
        return False

    def get_room_users(self, room: str) -> List[Dict[str, str]]:
        """Get list of active users in a specified room."""
        users: List[Dict[str, str]] = []
        with self._lock:
            s_ids = self._room_members.get(room, set())
            for s_id in s_ids:
                sess = self._sessions.get(s_id)
                if sess and sess.username:
                    users.append(sess.info_dict())
        return users
