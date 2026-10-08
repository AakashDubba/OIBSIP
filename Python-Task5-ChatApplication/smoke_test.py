"""Runtime End-to-End Smoke Test for ClinicFlow AI Secure Clinical Messaging Hub.

Validates complete real concurrent TCP socket communication, PBKDF2 authentication,
room segregation, role permissions, Unicode/emoji messaging, history replay, and GUI initialization.
Uses isolated temporary SQLite database cleaned up automatically upon exit.
"""

from __future__ import annotations

import os
import queue
import sys
import tempfile
import time
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from src.client.client import ClinicalChatClient
from src.client.gui import ClinicalChatGUI
from src.protocol.schemas import ClinicalRoom, MessageType, Packet, Role
from src.server.db import DatabaseManager
from src.server.server import ClinicalChatServer


def run_smoke_test() -> None:
    print("=== 1. Starting ClinicFlow AI Multi-Client Runtime Smoke Test ===")

    # 1. Setup isolated temporary SQLite database
    temp_dir = tempfile.TemporaryDirectory()
    temp_db_path = Path(temp_dir.name) / "smoke_clinical_chat.db"
    print(f"[OK] Initialized ephemeral test database at {temp_db_path}")

    db_manager = DatabaseManager(temp_db_path)

    # 2. Start TCP Socket Server on ephemeral port (port=0 binds to random available port)
    server = ClinicalChatServer(host="127.0.0.1", port=0, db_manager=db_manager)
    server.start()
    server_port = server.port
    print(f"[OK] ClinicFlow TCP Server running on 127.0.0.1:{server_port}")

    # Client Packet Collectors
    doctor_packets: queue.Queue[Packet] = queue.Queue()
    nurse_packets: queue.Queue[Packet] = queue.Queue()

    client_doctor = ClinicalChatClient(on_packet_received=lambda p: doctor_packets.put(p))
    client_nurse = ClinicalChatClient(on_packet_received=lambda p: nurse_packets.put(p))

    try:
        # 3. Connect concurrent clients
        ok_doc, _ = client_doctor.connect("127.0.0.1", server_port)
        ok_nur, _ = client_nurse.connect("127.0.0.1", server_port)
        assert ok_doc and ok_nur, "Both clients must connect successfully"
        print("[OK] Concurrent TCP connections established for Doctor and Nurse clients.")

        # 4. User Registration (PBKDF2-HMAC-SHA256 + 16-byte random salt)
        client_doctor.register("dr_carter", "CarterSecretPass1!", "DOCTOR")
        client_nurse.register("nurse_abby", "AbbySecretPass2!", "NURSE")
        time.sleep(0.15)

        # Drain registration confirmation packets
        while not doctor_packets.empty():
            doctor_packets.get_nowait()
        while not nurse_packets.empty():
            nurse_packets.get_nowait()

        # 5. Wrong password authentication rejection test
        client_doctor.login("dr_carter", "WrongPassword!")
        err_pack = doctor_packets.get(timeout=1.0)
        assert err_pack.type == MessageType.ERROR.value, f"Expected ERROR, got {err_pack.type}"
        print("[OK] Wrong password authentication attempt rejected cleanly with ERROR packet.")

        # 6. Legitimate authentication test
        client_doctor.login("dr_carter", "CarterSecretPass1!")
        client_nurse.login("nurse_abby", "AbbySecretPass2!")
        time.sleep(0.1)

        assert client_doctor.is_authenticated and client_doctor.role == "DOCTOR"
        assert client_nurse.is_authenticated and client_nurse.role == "NURSE"
        # Drain all queues before role-based authorization test
        while not doctor_packets.empty():
            doctor_packets.get_nowait()
        while not nurse_packets.empty():
            nurse_packets.get_nowait()

        # 7. Role-Based Room Authorization Test
        # Nurse attempting to enter #physician-consult must be rejected
        client_nurse.join_room(ClinicalRoom.PHYSICIAN_CONSULT.value)
        nurse_auth_err = nurse_packets.get(timeout=1.0)
        assert nurse_auth_err.type == MessageType.ERROR.value, f"Expected ERROR, got {nurse_auth_err.type}"
        print("[OK] Role-based authorization enforced: Nurse denied access to #physician-consult.")

        # Doctor enters #physician-consult -> must succeed
        client_doctor.join_room(ClinicalRoom.PHYSICIAN_CONSULT.value)
        time.sleep(0.1)
        assert client_doctor.current_room == ClinicalRoom.PHYSICIAN_CONSULT.value
        print("[OK] Doctor authorized and entered #physician-consult.")

        # 8. Room Segregation & Unicode/Emoji Transit Test
        # Both join #triage
        client_doctor.join_room(ClinicalRoom.TRIAGE.value)
        client_nurse.join_room(ClinicalRoom.TRIAGE.value)
        time.sleep(0.1)

        # Drain previous queues
        while not doctor_packets.empty():
            doctor_packets.get_nowait()
        while not nurse_packets.empty():
            nurse_packets.get_nowait()

        # Doctor sends emergency triage message with Unicode and clinical emojis
        test_msg = "Critical Alert: Patient BP dropping 🚨 Administer 50mg Epinephrine stat! 💉💊"
        client_doctor.send_chat_message(test_msg)

        # Nurse in #triage must receive broadcast
        received = nurse_packets.get(timeout=1.0)
        assert received.type == MessageType.MSG_BROADCAST.value
        assert received.payload["text"] == test_msg
        assert received.sender == "dr_carter"
        assert received.role == "DOCTOR"
        print(f"[OK] Unicode/emoji broadcast delivered in {received.room}: {received.payload['text']}")

        # Room Isolation check: Third client in #general must NOT receive the #triage message
        client_observer = ClinicalChatClient()
        client_observer.connect("127.0.0.1", server_port)
        client_observer.register("observer", "ObsPass123!", "NURSE")
        time.sleep(0.05)
        client_observer.login("observer", "ObsPass123!")
        time.sleep(0.05)
        assert client_observer.current_room == ClinicalRoom.GENERAL.value

        # Send another message in #triage
        client_nurse.send_chat_message("Epinephrine administered. Vitals steadying 🩺")
        time.sleep(0.1)

        # Verify observer in #general received nothing
        client_observer.sock.setblocking(False)  # type: ignore[union-attr]
        try:
            chunk = client_observer.sock.recv(1024)  # type: ignore[union-attr]
            assert False, "Observer in #general should not receive #triage messages!"
        except (BlockingIOError, OSError):
            pass  # Expected: zero bytes received
        print("[OK] Clinical room segregation verified: Messages in #triage do not leak to #general.")
        client_observer.disconnect()

        # 9. Persistent Message History Replay on Reconnect Test
        print("Testing message history replay after reconnect...")
        client_reconnect = ClinicalChatClient()
        reconnect_packets: queue.Queue[Packet] = queue.Queue()
        client_reconnect.on_packet_received = lambda p: reconnect_packets.put(p)
        client_reconnect.connect("127.0.0.1", server_port)
        client_reconnect.login("dr_carter", "CarterSecretPass1!")
        time.sleep(0.1)
        client_reconnect.join_room(ClinicalRoom.TRIAGE.value)
        time.sleep(0.1)

        history_found = False
        while not reconnect_packets.empty():
            p = reconnect_packets.get_nowait()
            if p.type == MessageType.HISTORY_RESP.value:
                messages = p.payload.get("messages", [])
                msg_texts = [m.get("message") for m in messages if isinstance(m, dict)]
                if test_msg in msg_texts:
                    history_found = True
                    break

        assert history_found, "Historical message replay must include persisted messages"
        print("[OK] Persistent SQLite history replay verified on room rejoin.")
        client_reconnect.disconnect()

        # 10. Desktop GUI Client Initialization Test (Programmatic/Headless)
        print("Testing Tkinter Desktop GUI client initialization...")
        gui_app = ClinicalChatGUI(default_host="127.0.0.1", default_port=server_port)
        gui_app.update_idletasks()
        gui_app.update()
        assert gui_app.winfo_exists()
        print("[OK] Tkinter GUI client initialized without unhandled exceptions.")
        gui_app.destroy()

        # 11. Graceful Disconnection
        client_doctor.disconnect()
        client_nurse.disconnect()
        assert not client_doctor.is_connected
        assert not client_nurse.is_connected
        print("[OK] Client connections terminated cleanly without dangling sockets.")

    finally:
        server.stop()
        time.sleep(0.1)
        try:
            temp_dir.cleanup()
            print("[OK] Ephemeral SQLite database deleted.")
        except Exception:
            pass

    print("=== TASK 5 SMOKE TEST COMPLETED SUCCESSFULLY WITH ZERO ERRORS ===")


if __name__ == "__main__":
    run_smoke_test()
