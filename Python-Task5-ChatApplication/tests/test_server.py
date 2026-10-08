"""Tests for ConnectionManager, room segregation, and role authorization."""

from __future__ import annotations

import socket
import pytest

from src.protocol.schemas import ClinicalRoom, MessageType, Packet, Role
from src.protocol.serializer import read_framed_packet
from src.server.connection_manager import ConnectionManager


def test_connection_manager_room_segregation() -> None:
    manager = ConnectionManager()

    # Create two pairs of connected socket endpoints
    s1_srv, s1_cli = socket.socketpair()
    s2_srv, s2_cli = socket.socketpair()

    try:
        # Register client 1 in #triage (as DOCTOR)
        sess1 = manager.register_client("s1", s1_srv)
        manager.authenticate_client("s1", "dr_alice", "DOCTOR")
        ok1, _ = manager.switch_room("s1", ClinicalRoom.TRIAGE.value)
        assert ok1 is True

        # Register client 2 in #general (as NURSE)
        sess2 = manager.register_client("s2", s2_srv)
        manager.authenticate_client("s2", "nurse_bob", "NURSE")
        assert sess2.current_room == ClinicalRoom.GENERAL.value

        # Broadcast message into #triage
        triage_msg = Packet.create(
            msg_type=MessageType.MSG_BROADCAST,
            sender="dr_alice",
            role=Role.DOCTOR,
            room=ClinicalRoom.TRIAGE,
            payload={"text": "Stat lab result for Bay 3 🧪"},
        )
        sent = manager.broadcast_to_room(ClinicalRoom.TRIAGE.value, triage_msg)
        assert sent == 1

        # Client 1 in #triage should receive the message
        received_by_1 = read_framed_packet(s1_cli)
        assert received_by_1 is not None
        assert received_by_1.payload["text"] == "Stat lab result for Bay 3 🧪"

        # Client 2 in #general must NOT receive anything (verify non-blocking zero bytes read)
        s2_cli.setblocking(False)
        try:
            chunk = s2_cli.recv(1024)
            assert False, "Client in #general should not receive #triage messages"
        except (BlockingIOError, socket.error):
            pass  # Expected: no bytes queued

    finally:
        s1_srv.close()
        s1_cli.close()
        s2_srv.close()
        s2_cli.close()


def test_role_based_room_access_control() -> None:
    manager = ConnectionManager()
    dummy_sock, _ = socket.socketpair()

    try:
        sess = manager.register_client("sess_nurse", dummy_sock)
        manager.authenticate_client("sess_nurse", "nurse_emma", "NURSE")

        # Nurse attempting to enter #physician-consult should be rejected
        ok, reason = manager.switch_room("sess_nurse", ClinicalRoom.PHYSICIAN_CONSULT.value)
        assert ok is False
        assert "requires DOCTOR or ADMIN" in reason

        # Nurse can enter #triage and #general
        ok_triage, _ = manager.switch_room("sess_nurse", ClinicalRoom.TRIAGE.value)
        assert ok_triage is True

        # Elevate to DOCTOR
        manager.authenticate_client("sess_nurse", "nurse_emma", "DOCTOR")
        ok_consult, _ = manager.switch_room("sess_nurse", ClinicalRoom.PHYSICIAN_CONSULT.value)
        assert ok_consult is True

    finally:
        dummy_sock.close()


def test_connection_cleanup_on_disconnect() -> None:
    manager = ConnectionManager()
    dummy_sock, _ = socket.socketpair()

    try:
        manager.register_client("s_disc", dummy_sock)
        manager.authenticate_client("s_disc", "temp_user", "NURSE")
        manager.switch_room("s_disc", ClinicalRoom.TRIAGE.value)

        assert len(manager.get_room_users(ClinicalRoom.TRIAGE.value)) == 1

        removed = manager.remove_client("s_disc")
        assert removed is not None
        assert len(manager.get_room_users(ClinicalRoom.TRIAGE.value)) == 0

    finally:
        dummy_sock.close()
