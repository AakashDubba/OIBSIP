"""Lightweight interactive terminal CLI client for ClinicFlow AI.

Supports headless debugging, automated test scripting, and command-line clinical messaging.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Optional

from src.client.client import ClinicalChatClient
from src.protocol.schemas import ClinicalRoom, MessageType, Packet, Role

logger = logging.getLogger(__name__)


def run_cli_client(host: str = "127.0.0.1", port: int = 8443) -> None:
    """Run interactive terminal CLI client loop."""
    print("=====================================================")
    print("   ClinicFlow AI — Terminal Clinical Client          ")
    print("   Type /help for command list, /exit to disconnect  ")
    print("=====================================================")

    def on_packet(packet: Packet) -> None:
        p_type = packet.type
        payload = packet.payload if isinstance(packet.payload, dict) else {}

        if p_type == MessageType.MSG_BROADCAST.value:
            text = payload.get("text", "")
            t = packet.timestamp[11:19]
            print(f"\n[{t}] [{packet.role}] {packet.sender}: {text}\nCLI > ", end="", flush=True)

        elif p_type == MessageType.SYSTEM_EVENT.value:
            msg = payload.get("message", "")
            print(f"\n[SYSTEM]: {msg}\nCLI > ", end="", flush=True)

        elif p_type == MessageType.AUTH_SUCCESS.value:
            user = payload.get("username", "")
            role = payload.get("role", "")
            room = payload.get("current_room", "")
            print(f"\n[AUTH SUCCESS]: Logged in as [{role}] {user} in {room}\nCLI > ", end="", flush=True)

        elif p_type == MessageType.JOIN_ROOM.value:
            room = payload.get("room", "")
            print(f"\n[ROOM SWITCH]: Active room is now {room}\nCLI > ", end="", flush=True)

        elif p_type == MessageType.USER_LIST.value:
            users = payload.get("users", [])
            user_strs = [f"[{u.get('role', '')}] {u.get('username', '')}" for u in users if isinstance(u, dict)]
            print(f"\n[ROOM STAFF]: {', '.join(user_strs) if user_strs else 'None'}\nCLI > ", end="", flush=True)

        elif p_type == MessageType.HISTORY_RESP.value:
            messages = payload.get("messages", [])
            print(f"\n--- ROOM HISTORY ({len(messages)} items) ---")
            for m in messages:
                if isinstance(m, dict):
                    t = str(m.get("timestamp", ""))[11:19]
                    print(f"[{t}] [{m.get('role', '')}] {m.get('sender', '')}: {m.get('message', '')}")
            print("------------------------------------------\nCLI > ", end="", flush=True)

        elif p_type == MessageType.ERROR.value:
            err = payload.get("error", "Error")
            print(f"\n[ERROR]: {err}\nCLI > ", end="", flush=True)

    def on_disconnect(reason: str) -> None:
        print(f"\n[DISCONNECTED]: {reason}")

    client = ClinicalChatClient(
        on_packet_received=on_packet,
        on_connection_lost=on_disconnect,
    )

    print(f"Connecting to {host}:{port}...")
    ok, conn_msg = client.connect(host, port)
    if not ok:
        print(f"[ERROR]: {conn_msg}")
        return

    print(f"[CONNECTED]: {conn_msg}\n")

    while client.is_connected:
        try:
            line = input("CLI > ").strip()
            if not line:
                continue

            if line.startswith("/"):
                parts = line.split()
                cmd = parts[0].lower()

                if cmd == "/exit":
                    client.disconnect()
                    break
                elif cmd == "/help":
                    print("Available commands:")
                    print("  /register <user> <pass> <role> (role: DOCTOR | NURSE | ADMIN)")
                    print("  /login <user> <pass>")
                    print("  /join <#room> (e.g., #triage, #physician-consult, #general)")
                    print("  /users")
                    print("  /history")
                    print("  /exit")
                elif cmd == "/register":
                    if len(parts) < 4:
                        print("Usage: /register <user> <pass> <role>")
                    else:
                        client.register(parts[1], parts[2], parts[3])
                elif cmd == "/login":
                    if len(parts) < 3:
                        print("Usage: /login <user> <pass>")
                    else:
                        client.login(parts[1], parts[2])
                elif cmd == "/join":
                    if len(parts) < 2:
                        print("Usage: /join <#room>")
                    else:
                        client.join_room(parts[1])
                elif cmd == "/users":
                    p = Packet.create(msg_type=MessageType.USER_LIST, sender=client.username or "cli", room=client.current_room)
                    client.send_packet(p)
                elif cmd == "/history":
                    client.request_history()
                else:
                    print(f"Unknown command '{cmd}'. Type /help for assistance.")
            else:
                if not client.is_authenticated:
                    print("[WARNING]: You must login first! Type: /login <user> <pass> or /register <user> <pass> <role>")
                else:
                    client.send_chat_message(line)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting CLI...")
            client.disconnect()
            break


if __name__ == "__main__":
    run_cli_client()
