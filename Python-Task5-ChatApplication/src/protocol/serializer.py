"""Binary length-prefixed framing and JSON serialization engine for TCP sockets.

Protocol Framing Specification:
[ 4 Bytes: Big-Endian Unsigned Integer (Payload Length) ] [ N Bytes: UTF-8 Encoded JSON Payload ]

Guarantees:
- Zero packet fragmentation or sticking.
- Full UTF-8 Unicode and emoji support without byte corruption.
- Strict payload length limits (default 1MB max) preventing DoS memory attacks.
"""

from __future__ import annotations

import json
import logging
import socket
import struct
from typing import Optional, Tuple

from src.protocol.schemas import Packet, validate_packet

logger = logging.getLogger(__name__)

HEADER_FORMAT = ">I"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 4 bytes
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1 MB safety ceiling


def serialize_packet(packet: Packet) -> bytes:
    """Validate, encode to UTF-8 JSON, and frame with a 4-byte length prefix."""
    valid, err = validate_packet(packet)
    if not valid:
        raise ValueError(f"Packet validation error: {err}")

    raw_json = json.dumps(packet.to_dict(), ensure_ascii=False)
    payload_bytes = raw_json.encode("utf-8")

    payload_length = len(payload_bytes)
    if payload_length > MAX_PAYLOAD_SIZE:
        raise ValueError(f"Payload size ({payload_length} bytes) exceeds safety ceiling ({MAX_PAYLOAD_SIZE} bytes).")

    header = struct.pack(HEADER_FORMAT, payload_length)
    return header + payload_bytes


def deserialize_payload(payload_bytes: bytes) -> Packet:
    """Decode raw UTF-8 JSON bytes into a typed Packet schema."""
    json_str = payload_bytes.decode("utf-8")
    data = json.loads(json_str)
    packet = Packet.from_dict(data)
    valid, err = validate_packet(packet)
    if not valid:
        raise ValueError(f"Deserialized packet invalid: {err}")
    return packet


def read_exact(sock: socket.socket, num_bytes: int) -> Optional[bytes]:
    """Read exactly num_bytes from a TCP socket stream, handling chunked fragments."""
    buffer = bytearray()
    while len(buffer) < num_bytes:
        try:
            chunk = sock.recv(num_bytes - len(buffer))
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError, OSError):
            return None

        if not chunk:  # Remote peer closed connection
            return None
        buffer.extend(chunk)
    return bytes(buffer)


def read_framed_packet(sock: socket.socket) -> Optional[Packet]:
    """Read next length-prefixed packet from TCP socket stream."""
    # 1. Read 4-byte header
    header_bytes = read_exact(sock, HEADER_SIZE)
    if not header_bytes:
        return None

    # 2. Unpack payload length
    payload_length, = struct.unpack(HEADER_FORMAT, header_bytes)
    if payload_length > MAX_PAYLOAD_SIZE:
        logger.error("Incoming packet declared length %d exceeds max %d", payload_length, MAX_PAYLOAD_SIZE)
        return None

    # 3. Read exact payload bytes
    payload_bytes = read_exact(sock, payload_length)
    if not payload_bytes:
        return None

    # 4. Deserialize into schema
    try:
        return deserialize_payload(payload_bytes)
    except Exception as exc:
        logger.error("Failed to deserialize framed packet: %s", exc)
        return None


def send_framed_packet(sock: socket.socket, packet: Packet) -> bool:
    """Serialize and send packet over TCP socket with error handling."""
    try:
        framed_data = serialize_packet(packet)
        sock.sendall(framed_data)
        return True
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError) as exc:
        logger.debug("Failed to send framed packet to peer: %s", exc)
        return False
