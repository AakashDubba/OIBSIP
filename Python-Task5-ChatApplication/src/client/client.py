"""Dual-threaded Socket Client Engine for ClinicFlow messaging.

Features:
- Background listener thread consuming framed binary packets over TCP.
- Thread-safe sending pipeline.
- Callback architecture for packet reception and connection lifecycle events.
"""

from __future__ import annotations

import logging
import socket
import threading
from typing import Callable, Optional, Tuple

from src.protocol.schemas import ClinicalRoom, MessageType, Packet, Role
from src.protocol.serializer import read_framed_packet, send_framed_packet

logger = logging.getLogger(__name__)


class ClinicalChatClient:
    """Threaded TCP Socket client for ClinicFlow network protocol."""

    def __init__(
        self,
        on_packet_received: Optional[Callable[[Packet], None]] = None,
        on_connection_lost: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.on_packet_received = on_packet_received
        self.on_connection_lost = on_connection_lost

        self.sock: Optional[socket.socket] = None
        self.username: Optional[str] = None
        self.role: Optional[str] = None
        self.current_room: str = ClinicalRoom.GENERAL.value
        self.is_connected = False
        self.is_authenticated = False

        self._recv_thread: Optional[threading.Thread] = None
        self._send_lock = threading.Lock()

    def connect(self, host: str = "127.0.0.1", port: int = 8443) -> Tuple[bool, str]:
        """Establish TCP socket connection to the server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self.is_connected = True

            self._recv_thread = threading.Thread(
                target=self._receiver_loop,
                name="ClientReceiverLoop",
                daemon=True,
            )
            self._recv_thread.start()
            logger.info("Connected to ClinicFlow server at %s:%d", host, port)
            return True, f"Connected to {host}:{port}"
        except Exception as exc:
            self.is_connected = False
            self.sock = None
            logger.error("Connection failed to %s:%d: %s", host, port, exc)
            return False, f"Connection failed: {exc}"

    def _receiver_loop(self) -> None:
        """Background daemon thread listening for framed packets."""
        while self.is_connected and self.sock:
            try:
                packet = read_framed_packet(self.sock)
                if not packet:
                    break

                # Update internal state if auth packet
                if packet.type == MessageType.AUTH_SUCCESS.value:
                    payload = packet.payload if isinstance(packet.payload, dict) else {}
                    self.username = str(payload.get("username", ""))
                    self.role = str(payload.get("role", "NURSE"))
                    self.current_room = str(payload.get("current_room", self.current_room))
                    self.is_authenticated = True
                elif packet.type == MessageType.JOIN_ROOM.value:
                    payload = packet.payload if isinstance(packet.payload, dict) else {}
                    self.current_room = str(payload.get("room", self.current_room))

                if self.on_packet_received:
                    try:
                        self.on_packet_received(packet)
                    except Exception as cb_exc:
                        logger.error("Exception in packet callback: %s", cb_exc)

            except Exception as exc:
                logger.warning("Receiver loop encountered error: %s", exc)
                break

        self._cleanup_connection("Connection closed by server or network interruption.")

    def _cleanup_connection(self, reason: str) -> None:
        if not self.is_connected:
            return
        self.is_connected = False
        self.is_authenticated = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        logger.info("Client disconnected: %s", reason)
        if self.on_connection_lost:
            try:
                self.on_connection_lost(reason)
            except Exception:
                pass

    def send_packet(self, packet: Packet) -> bool:
        """Thread-safe transmission of a framed packet."""
        if not self.is_connected or not self.sock:
            return False
        with self._send_lock:
            return send_framed_packet(self.sock, packet)

    # ---------------- CONVENIENCE PROTOCOL METHODS ----------------

    def register(self, username: str, password: str, role: str) -> bool:
        """Transmit registration packet."""
        packet = Packet.create(
            msg_type=MessageType.REGISTER,
            sender=username,
            role=role,
            payload={"username": username, "password": password, "role": role},
        )
        return self.send_packet(packet)

    def login(self, username: str, password: str) -> bool:
        """Transmit login packet."""
        packet = Packet.create(
            msg_type=MessageType.LOGIN,
            sender=username,
            payload={"username": username, "password": password},
        )
        return self.send_packet(packet)

    def join_room(self, room_name: str) -> bool:
        """Transmit join room request."""
        packet = Packet.create(
            msg_type=MessageType.JOIN_ROOM,
            sender=self.username or "anonymous",
            role=self.role or "NURSE",
            room=room_name,
            payload={"room": room_name},
        )
        return self.send_packet(packet)

    def send_chat_message(self, text: str) -> bool:
        """Send chat message to current active clinical room."""
        if not text.strip():
            return False
        packet = Packet.create(
            msg_type=MessageType.SEND_MSG,
            sender=self.username or "anonymous",
            role=self.role or "NURSE",
            room=self.current_room,
            payload={"text": text.strip()},
        )
        return self.send_packet(packet)

    def request_history(self, room: Optional[str] = None) -> bool:
        """Request historical message replay."""
        target_room = room or self.current_room
        packet = Packet.create(
            msg_type=MessageType.HISTORY_REQ,
            sender=self.username or "anonymous",
            room=target_room,
        )
        return self.send_packet(packet)

    def disconnect(self) -> None:
        """Gracefully disconnect from server."""
        if self.is_connected and self.sock:
            try:
                disc_pack = Packet.create(
                    msg_type=MessageType.DISCONNECT,
                    sender=self.username or "anonymous",
                )
                self.send_packet(disc_pack)
            except Exception:
                pass
        self._cleanup_connection("User disconnected.")
