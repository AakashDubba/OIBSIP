"""Concurrent multi-client TCP Socket Server for ClinicFlow AI Secure Messaging Hub.

Handles framed message routing, authentication, room switching, audit logging, and history replay.
"""

from __future__ import annotations

import logging
import socket
import threading
import uuid
from typing import Optional

from src.protocol.schemas import ClinicalRoom, MessageType, Packet, Role
from src.protocol.serializer import read_framed_packet, send_framed_packet
from src.server.connection_manager import ConnectionManager
from src.server.db import DatabaseManager

logger = logging.getLogger(__name__)


class ClinicalChatServer:
    """Multi-client TCP Server with role-based routing and persistent audit trail."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8443,
        db_manager: Optional[DatabaseManager] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.db = db_manager or DatabaseManager()
        self.manager = ConnectionManager()

        self._server_sock: Optional[socket.socket] = None
        self._is_running = False
        self._accept_thread: Optional[threading.Thread] = None
        self._client_threads: list[threading.Thread] = []

    def start(self) -> None:
        """Bind TCP socket and launch client listener loop."""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(50)
        self._is_running = True

        actual_port = self._server_sock.getsockname()[1]
        self.port = actual_port

        logger.info("ClinicFlow TCP Server listening on %s:%d", self.host, self.port)

        self._accept_thread = threading.Thread(
            target=self._accept_loop,
            name="ServerAcceptLoop",
            daemon=True,
        )
        self._accept_thread.start()

    def _accept_loop(self) -> None:
        """Accept incoming client TCP connections."""
        while self._is_running and self._server_sock:
            try:
                client_sock, addr = self._server_sock.accept()
            except (OSError, socket.error):
                break

            session_id = str(uuid.uuid4())[:8]
            logger.info("Accepted connection from %s (Session ID: %s)", addr, session_id)
            session = self.manager.register_client(session_id, client_sock)

            t = threading.Thread(
                target=self._client_handler_loop,
                args=(session_id, client_sock),
                name=f"ClientHandler-{session_id}",
                daemon=True,
            )
            self._client_threads.append(t)
            t.start()

    def _client_handler_loop(self, session_id: str, client_sock: socket.socket) -> None:
        """Message processing loop for an individual connected client."""
        try:
            while self._is_running:
                packet = read_framed_packet(client_sock)
                if not packet:
                    break  # Client disconnected

                self._dispatch_packet(session_id, packet)

        except Exception as exc:
            logger.warning("Session [%s] handler encountered error: %s", session_id, exc)
        finally:
            self._handle_client_disconnect(session_id, client_sock)

    def _dispatch_packet(self, session_id: str, packet: Packet) -> None:
        """Route framed packet to appropriate service handler."""
        session = self.manager.get_session(session_id)
        if not session:
            return

        p_type = packet.type

        if p_type == MessageType.REGISTER.value:
            self._handle_register(session_id, packet)
        elif p_type == MessageType.LOGIN.value:
            self._handle_login(session_id, packet)
        elif p_type == MessageType.JOIN_ROOM.value:
            self._handle_join_room(session_id, packet)
        elif p_type == MessageType.SEND_MSG.value:
            self._handle_send_msg(session_id, packet)
        elif p_type == MessageType.HISTORY_REQ.value:
            self._handle_history_req(session_id, packet)
        elif p_type == MessageType.USER_LIST.value:
            self._handle_user_list(session_id, packet)
        elif p_type == MessageType.DISCONNECT.value:
            session.sock.close()
        else:
            self.manager.send_to_session(
                session_id,
                Packet.error(f"Unknown or unsupported message type '{p_type}'.", room=session.current_room),
            )

    # ---------------- HANDLER IMPLEMENTATIONS ----------------

    def _handle_register(self, session_id: str, packet: Packet) -> None:
        payload = packet.payload if isinstance(packet.payload, dict) else {}
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "")).strip()
        role = str(payload.get("role", "NURSE")).strip()

        if not Role.is_valid(role):
            self.manager.send_to_session(
                session_id,
                Packet.error(f"Invalid role '{role}'. Permitted roles: DOCTOR, NURSE, ADMIN."),
            )
            return

        ok, msg = self.db.register_user(username, password, role)
        if ok:
            resp = Packet.create(
                msg_type=MessageType.SYSTEM_EVENT,
                sender="SERVER",
                role=Role.ADMIN,
                payload={"status": "REGISTERED", "message": msg},
            )
        else:
            resp = Packet.error(msg)
        self.manager.send_to_session(session_id, resp)

    def _handle_login(self, session_id: str, packet: Packet) -> None:
        payload = packet.payload if isinstance(packet.payload, dict) else {}
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "")).strip()

        ok, role, msg = self.db.authenticate_user(username, password)
        if not ok or not role:
            self.manager.send_to_session(session_id, Packet.error(msg))
            return

        # Authenticate session
        self.manager.authenticate_client(session_id, username, role)
        session = self.manager.get_session(session_id)
        current_room = session.current_room if session else ClinicalRoom.GENERAL.value

        # Send AUTH_SUCCESS confirmation
        auth_pack = Packet.create(
            msg_type=MessageType.AUTH_SUCCESS,
            sender="SERVER",
            role=role,
            room=current_room,
            payload={
                "username": username,
                "role": role,
                "current_room": current_room,
                "available_rooms": ClinicalRoom.all_rooms(),
                "message": msg,
            },
        )
        self.manager.send_to_session(session_id, auth_pack)

        # Notify room members of arrival
        arrival_event = Packet.system_event(
            f"Staff member [{role}] {username} has joined {current_room}.",
            room=current_room,
        )
        self.manager.broadcast_to_room(current_room, arrival_event, exclude_session_id=session_id)

        # Replay room message history
        self._send_room_history(session_id, current_room)

        # Broadcast updated user list to room members
        self._broadcast_room_user_list(current_room)

    def _handle_join_room(self, session_id: str, packet: Packet) -> None:
        session = self.manager.get_session(session_id)
        if not session or not session.is_authenticated:
            self.manager.send_to_session(session_id, Packet.error("Authentication required."))
            return

        payload = packet.payload if isinstance(packet.payload, dict) else {}
        target_room = str(payload.get("room", packet.room)).strip()
        old_room = session.current_room

        ok, msg = self.manager.switch_room(session_id, target_room)
        if not ok:
            self.manager.send_to_session(session_id, Packet.error(msg, room=old_room))
            return

        # Announce departure in old room
        depart_msg = Packet.system_event(
            f"[{session.role}] {session.username} left the room.",
            room=old_room,
        )
        self.manager.broadcast_to_room(old_room, depart_msg)
        self._broadcast_room_user_list(old_room)

        # Confirm switch to client
        switch_confirm = Packet.create(
            msg_type=MessageType.JOIN_ROOM,
            sender="SERVER",
            role=Role.ADMIN,
            room=target_room,
            payload={"status": "JOINED", "room": target_room, "message": msg},
        )
        self.manager.send_to_session(session_id, switch_confirm)

        # Announce arrival in new room
        arrival_msg = Packet.system_event(
            f"[{session.role}] {session.username} joined {target_room}.",
            room=target_room,
        )
        self.manager.broadcast_to_room(target_room, arrival_msg, exclude_session_id=session_id)

        # Replay room history for new room
        self._send_room_history(session_id, target_room)
        self._broadcast_room_user_list(target_room)

    def _handle_send_msg(self, session_id: str, packet: Packet) -> None:
        session = self.manager.get_session(session_id)
        if not session or not session.is_authenticated:
            self.manager.send_to_session(session_id, Packet.error("Authentication required."))
            return

        payload = packet.payload if isinstance(packet.payload, dict) else {}
        text_content = str(payload.get("text", "")).strip()
        if not text_content:
            return

        target_room = session.current_room
        sender = session.username or "Anonymous"
        role = session.role or "NURSE"

        # 1. Persist to SQLite audit store
        self.db.store_message(
            packet_id=packet.packet_id,
            room=target_room,
            sender=sender,
            role=role,
            message=text_content,
            timestamp=packet.timestamp,
        )

        # 2. Broadcast strictly to members of target_room
        broadcast_packet = Packet.create(
            msg_type=MessageType.MSG_BROADCAST,
            sender=sender,
            role=role,
            room=target_room,
            payload={"text": text_content},
            packet_id=packet.packet_id,
        )
        self.manager.broadcast_to_room(target_room, broadcast_packet)

    def _handle_history_req(self, session_id: str, packet: Packet) -> None:
        session = self.manager.get_session(session_id)
        if not session or not session.is_authenticated:
            return
        target_room = packet.room or session.current_room
        self._send_room_history(session_id, target_room)

    def _handle_user_list(self, session_id: str, packet: Packet) -> None:
        session = self.manager.get_session(session_id)
        if not session:
            return
        target_room = packet.room or session.current_room
        users = self.manager.get_room_users(target_room)
        resp = Packet.create(
            msg_type=MessageType.USER_LIST,
            sender="SERVER",
            role=Role.ADMIN,
            room=target_room,
            payload={"users": users},
        )
        self.manager.send_to_session(session_id, resp)

    def _send_room_history(self, session_id: str, room: str) -> None:
        history = self.db.get_room_history(room, limit=50)
        resp = Packet.create(
            msg_type=MessageType.HISTORY_RESP,
            sender="SERVER",
            role=Role.ADMIN,
            room=room,
            payload={"messages": history},
        )
        self.manager.send_to_session(session_id, resp)

    def _broadcast_room_user_list(self, room: str) -> None:
        users = self.manager.get_room_users(room)
        pack = Packet.create(
            msg_type=MessageType.USER_LIST,
            sender="SERVER",
            role=Role.ADMIN,
            room=room,
            payload={"users": users},
        )
        self.manager.broadcast_to_room(room, pack)

    def _handle_client_disconnect(self, session_id: str, sock: socket.socket) -> None:
        session = self.manager.remove_client(session_id)
        try:
            sock.close()
        except Exception:
            pass

        if session and session.username and session.is_authenticated:
            leave_pack = Packet.system_event(
                f"[{session.role}] {session.username} disconnected.",
                room=session.current_room,
            )
            self.manager.broadcast_to_room(session.current_room, leave_pack)
            self._broadcast_room_user_list(session.current_room)

    def stop(self) -> None:
        """Gracefully terminate server and close active connections."""
        self._is_running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
        logger.info("ClinicFlow TCP Server terminated cleanly.")
