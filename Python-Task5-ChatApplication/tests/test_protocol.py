"""Tests for binary length-prefixed framing, schema validation, and Unicode/emoji transit."""

from __future__ import annotations

import io
import socket
import struct
import pytest

from src.protocol.schemas import ClinicalRoom, MessageType, Packet, Role, validate_packet
from src.protocol.serializer import (
    HEADER_SIZE,
    deserialize_payload,
    read_exact,
    read_framed_packet,
    send_framed_packet,
    serialize_packet,
)


def test_packet_creation_and_validation() -> None:
    p = Packet.create(
        msg_type=MessageType.SEND_MSG,
        sender="dr_watson",
        role=Role.DOCTOR,
        room=ClinicalRoom.TRIAGE,
        payload={"text": "Patient vitals stabilized 🩺"},
    )
    assert p.packet_id
    assert p.type == "SEND_MSG"
    assert p.sender == "dr_watson"
    assert p.role == "DOCTOR"
    assert p.room == "#triage"

    valid, err = validate_packet(p)
    assert valid is True
    assert err is None


def test_packet_invalid_schema() -> None:
    # Invalid room
    p_bad_room = Packet(
        packet_id="1234",
        type="SEND_MSG",
        sender="nurse_joy",
        role="NURSE",
        room="#invalid-unauthorized-room",
        payload={},
        timestamp="2026-10-08T00:00",
    )
    valid, err = validate_packet(p_bad_room)
    assert valid is False
    assert "Unauthorized room" in (err or "")

    # Invalid message type
    p_bad_type = Packet.create(msg_type="NON_EXISTENT_TYPE")
    valid, err = validate_packet(p_bad_type)
    assert valid is False
    assert "Invalid message type" in (err or "")


def test_binary_length_prefix_framing() -> None:
    text_content = "Stat ECG needed in ICU! 🚨 Room 4B 💉"
    original = Packet.create(
        msg_type=MessageType.SEND_MSG,
        sender="dr_smith",
        role=Role.DOCTOR,
        room=ClinicalRoom.TRIAGE,
        payload={"text": text_content},
    )

    framed_bytes = serialize_packet(original)

    # 1. Verify 4-byte big endian header
    assert len(framed_bytes) > HEADER_SIZE
    payload_len, = struct.unpack(">I", framed_bytes[:HEADER_SIZE])
    assert payload_len == len(framed_bytes) - HEADER_SIZE

    # 2. Unframe and verify payload integrity
    unframed_packet = deserialize_payload(framed_bytes[HEADER_SIZE:])
    assert unframed_packet.packet_id == original.packet_id
    assert unframed_packet.payload["text"] == text_content


def test_socket_chunked_streaming() -> None:
    """Test that read_framed_packet correctly reconstructs fragmented TCP packet chunks."""
    sock_server, sock_client = socket.socketpair()

    try:
        p = Packet.create(
            msg_type=MessageType.MSG_BROADCAST,
            sender="nurse_clara",
            role=Role.NURSE,
            room=ClinicalRoom.GENERAL,
            payload={"text": "Shift change summary: All vitals verified 📋💊"},
        )
        framed = serialize_packet(p)

        # Send in tiny fragmented chunks simulating TCP packet fragmentation
        chunk1 = framed[:5]
        chunk2 = framed[5:20]
        chunk3 = framed[20:]

        sock_client.sendall(chunk1)
        sock_client.sendall(chunk2)
        sock_client.sendall(chunk3)

        reconstructed = read_framed_packet(sock_server)
        assert reconstructed is not None
        assert reconstructed.packet_id == p.packet_id
        assert reconstructed.payload["text"] == "Shift change summary: All vitals verified 📋💊"
        assert reconstructed.sender == "nurse_clara"

    finally:
        sock_server.close()
        sock_client.close()


def test_oversized_payload_rejection() -> None:
    huge_text = "A" * (1024 * 1024 + 10)
    huge_packet = Packet.create(
        msg_type=MessageType.SEND_MSG,
        payload={"text": huge_text},
    )

    with pytest.raises(ValueError, match="exceeds safety ceiling"):
        serialize_packet(huge_packet)
