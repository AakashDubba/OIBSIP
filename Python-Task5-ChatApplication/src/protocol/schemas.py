"""Typed dataclass schemas and enumerations for ClinicFlow messaging protocol."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class MessageType(str, Enum):
    """Protocol message action types."""
    REGISTER = "REGISTER"
    LOGIN = "LOGIN"
    AUTH_SUCCESS = "AUTH_SUCCESS"
    JOIN_ROOM = "JOIN_ROOM"
    LEAVE_ROOM = "LEAVE_ROOM"
    SEND_MSG = "SEND_MSG"
    MSG_BROADCAST = "MSG_BROADCAST"
    HISTORY_REQ = "HISTORY_REQ"
    HISTORY_RESP = "HISTORY_RESP"
    USER_LIST = "USER_LIST"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    ERROR = "ERROR"
    DISCONNECT = "DISCONNECT"


class Role(str, Enum):
    """Medical staff roles with authorization policies."""
    DOCTOR = "DOCTOR"
    NURSE = "NURSE"
    ADMIN = "ADMIN"

    @classmethod
    def is_valid(cls, role_str: str) -> bool:
        return role_str.upper() in cls._value2member_map_


class ClinicalRoom(str, Enum):
    """Segregated departmental clinical rooms."""
    TRIAGE = "#triage"
    PHYSICIAN_CONSULT = "#physician-consult"
    GENERAL = "#general"

    @classmethod
    def all_rooms(cls) -> List[str]:
        return [r.value for r in cls]

    @classmethod
    def is_valid(cls, room_str: str) -> bool:
        return room_str in cls._value2member_map_


@dataclass
class Packet:
    """Canonical framed wire message packet."""
    packet_id: str
    type: str
    sender: str
    role: str
    room: str
    payload: Any
    timestamp: str

    @classmethod
    def create(
        cls,
        msg_type: MessageType | str,
        sender: str = "anonymous",
        role: Role | str = "NURSE",
        room: ClinicalRoom | str = "#general",
        payload: Any = None,
        packet_id: Optional[str] = None,
    ) -> Packet:
        """Create a new typed message packet with timestamp and UUID."""
        type_str = msg_type.value if isinstance(msg_type, MessageType) else str(msg_type)
        role_str = role.value if isinstance(role, Role) else str(role)
        room_str = room.value if isinstance(room, ClinicalRoom) else str(room)
        return cls(
            packet_id=packet_id or str(uuid.uuid4())[:8],
            type=type_str,
            sender=sender.strip(),
            role=role_str.upper(),
            room=room_str,
            payload=payload if payload is not None else {},
            timestamp=datetime.now().isoformat(),
        )

    @classmethod
    def error(cls, error_msg: str, room: str = "#general", ref_id: Optional[str] = None) -> Packet:
        """Construct structured error response packet."""
        return cls.create(
            msg_type=MessageType.ERROR,
            sender="SERVER",
            role=Role.ADMIN,
            room=room,
            payload={"error": error_msg, "ref_id": ref_id or ""},
        )

    @classmethod
    def system_event(cls, message: str, room: str = "#general") -> Packet:
        """Construct a system alert notification packet."""
        return cls.create(
            msg_type=MessageType.SYSTEM_EVENT,
            sender="SYSTEM",
            role=Role.ADMIN,
            room=room,
            payload={"message": message},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert packet to plain dictionary for JSON serialization."""
        return {
            "packet_id": self.packet_id,
            "type": self.type,
            "sender": self.sender,
            "role": self.role,
            "room": self.room,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Packet:
        """Hydrate packet from parsed JSON dictionary."""
        return cls(
            packet_id=str(data.get("packet_id", str(uuid.uuid4())[:8])),
            type=str(data.get("type", "UNKNOWN")),
            sender=str(data.get("sender", "anonymous")),
            role=str(data.get("role", "NURSE")).upper(),
            room=str(data.get("room", "#general")),
            payload=data.get("payload", {}),
            timestamp=str(data.get("timestamp", datetime.now().isoformat())),
        )


def validate_packet(packet: Packet) -> Tuple[bool, Optional[str]]:
    """Strictly validate packet schemas before routing or serialization."""
    if not packet.packet_id or not packet.packet_id.strip():
        return False, "Missing packet_id."

    valid_types = {m.value for m in MessageType}
    if packet.type not in valid_types:
        return False, f"Invalid message type '{packet.type}'."

    if not packet.sender:
        return False, "Missing sender field."

    if packet.room and packet.room not in ClinicalRoom.all_rooms():
        return False, f"Unauthorized room '{packet.room}'. Allowed: {ClinicalRoom.all_rooms()}."

    return True, None
