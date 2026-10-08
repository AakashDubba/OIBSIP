"""Focused verification test for GUI notification and status update mechanism upon incoming messages/events."""

from __future__ import annotations

from src.client.gui import ClinicalChatGUI
from src.protocol.schemas import ClinicalRoom, MessageType, Packet, Role


def test_gui_incoming_message_and_system_event_notifications() -> None:
    """Verify GUI notification/status mechanism triggers cleanly on incoming packets."""
    # 1. Initialize GUI window
    app = ClinicalChatGUI()

    try:
        # Initial status check
        assert "Ready" in app.status_bar.cget("text")

        # 2. Simulate incoming clinical chat message packet
        msg_packet = Packet.create(
            msg_type=MessageType.MSG_BROADCAST,
            sender="dr_watson",
            role=Role.DOCTOR,
            room=ClinicalRoom.TRIAGE,
            payload={"text": "Patient vitals stable in Bay 4 🩺"},
        )

        # Enqueue packet through socket receiver handler
        app._on_packet_received(msg_packet)

        # Drain packet queue on GUI thread
        app._process_packet_queue()
        app.update_idletasks()

        # Verify status notification updated for incoming message
        status_text = app.status_bar.cget("text")
        assert status_text == "New message from [DOCTOR] dr_watson in #triage", (
            f"Expected notification status not found. Actual: '{status_text}'"
        )

        # Verify message text widget updated with content
        chat_content = app.msg_display.get("1.0", "end")
        assert "dr_watson" in chat_content
        assert "Patient vitals stable in Bay 4 🩺" in chat_content

        # 3. Simulate incoming critical system event notification
        system_alert = "Critical Alert: Code Blue in Room 204 🚨"
        event_packet = Packet.system_event(system_alert, room=ClinicalRoom.TRIAGE.value)

        # Enqueue system event
        app._on_packet_received(event_packet)
        app._process_packet_queue()
        app.update_idletasks()

        # Verify status notification updated for system event
        status_after_event = app.status_bar.cget("text")
        assert status_after_event == system_alert, (
            f"Expected system event notification not found. Actual: '{status_after_event}'"
        )

        # Verify message history contains system event
        chat_content_after_event = app.msg_display.get("1.0", "end")
        assert system_alert in chat_content_after_event

    finally:
        # Clean teardown
        app.destroy()
