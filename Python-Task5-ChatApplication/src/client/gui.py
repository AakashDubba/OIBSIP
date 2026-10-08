"""Modern Desktop GUI Client for ClinicFlow AI Secure Clinical Messaging Hub.

Built with Python Standard Library (tkinter + ttk).
Features:
- Dark-mode clinical dashboard styling.
- Registration and Login authentication view with role selection.
- Segregated room switcher (#triage, #physician-consult, #general).
- Rich message history display with color-coded role tags ([DOCTOR], [NURSE], [ADMIN]).
- Active medical staff user list.
- Message entry bar supporting Unicode & clinical emojis.
- Non-intrusive status notification bar for alerts and room transitions.
- Thread-safe socket event marshaling via self.after().
"""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

from src.client.client import ClinicalChatClient
from src.protocol.schemas import ClinicalRoom, MessageType, Packet, Role

logger = logging.getLogger(__name__)

# Dark Theme Palette
BG_DARK = "#121418"
BG_CARD = "#1c1f26"
BG_SIDEBAR = "#161920"
BG_INPUT = "#222733"
TEXT_PRIMARY = "#f3f4f6"
TEXT_MUTED = "#9ca3af"
ACCENT_BLUE = "#3b82f6"
ACCENT_CYAN = "#38bdf8"
ACCENT_GREEN = "#4ade80"
ACCENT_AMBER = "#fbbf24"
ACCENT_RED = "#f87171"


class ClinicalChatGUI(tk.Tk):
    """Main desktop interface for ClinicFlow AI clinical staff."""

    def __init__(
        self,
        client: Optional[ClinicalChatClient] = None,
        default_host: str = "127.0.0.1",
        default_port: int = 8443,
    ) -> None:
        super().__init__()

        self.title("ClinicFlow AI — Secure Clinical Messaging Hub")
        self.geometry("1000x700")
        self.minsize(850, 600)
        self.configure(bg=BG_DARK)

        self.chat_client = client or ClinicalChatClient(
            on_packet_received=self._on_packet_received,
            on_connection_lost=self._on_connection_lost,
        )
        self.default_host = default_host
        self.default_port = default_port

        self._packet_queue: queue.Queue[Packet] = queue.Queue()

        self._setup_styles()
        self._create_widgets()

        # Handle window closure
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Start periodic queue processor
        self.after(50, self._process_packet_queue)

    def _setup_styles(self) -> None:
        """Configure ttk styles for dark clinical UI."""
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=BG_DARK, foreground=TEXT_PRIMARY, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG_DARK)
        style.configure("Card.TFrame", background=BG_CARD)
        style.configure("Sidebar.TFrame", background=BG_SIDEBAR)

        style.configure(
            "TButton",
            background="#2563eb",
            foreground="#ffffff",
            padding=6,
            borderwidth=0,
            font=("Segoe UI", 10, "bold"),
        )
        style.map("TButton", background=[("active", "#1d4ed8")])

        style.configure(
            "Room.TButton",
            background="#374151",
            foreground="#e5e7eb",
            padding=5,
            anchor="w",
            font=("Segoe UI", 10),
        )
        style.map("Room.TButton", background=[("active", "#4b5563")])

        style.configure("TLabel", background=BG_DARK, foreground=TEXT_PRIMARY)
        style.configure("Card.TLabel", background=BG_CARD, foreground=TEXT_PRIMARY)
        style.configure("Status.TLabel", background=BG_SIDEBAR, foreground=TEXT_MUTED, font=("Segoe UI", 9))

    def _create_widgets(self) -> None:
        """Construct the split-screen clinical workspace."""
        # Top Header Bar
        self.header_frame = tk.Frame(self, bg=BG_CARD, height=54)
        self.header_frame.pack(side="top", fill="x")

        self.title_label = tk.Label(
            self.header_frame,
            text="🏥 ClinicFlow AI Hub",
            font=("Segoe UI", 15, "bold"),
            bg=BG_CARD,
            fg=ACCENT_CYAN,
        )
        self.title_label.pack(side="left", padx=16, pady=12)

        self.user_badge = tk.Label(
            self.header_frame,
            text="[DISCONNECTED]",
            font=("Segoe UI", 11, "bold"),
            bg=BG_CARD,
            fg=TEXT_MUTED,
        )
        self.user_badge.pack(side="right", padx=16, pady=12)

        self.room_badge = tk.Label(
            self.header_frame,
            text="Room: #general",
            font=("Segoe UI", 11),
            bg=BG_CARD,
            fg=ACCENT_GREEN,
        )
        self.room_badge.pack(side="right", padx=12, pady=12)

        # Main Workspace Container
        self.main_container = tk.Frame(self, bg=BG_DARK)
        self.main_container.pack(side="top", fill="both", expand=True)

        # --- Left Sidebar: Room Switcher & Staff List ---
        self.sidebar_frame = tk.Frame(self.main_container, bg=BG_SIDEBAR, width=220)
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        # Rooms Title
        tk.Label(
            self.sidebar_frame,
            text="CLINICAL ROOMS",
            font=("Segoe UI", 9, "bold"),
            bg=BG_SIDEBAR,
            fg=TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(16, 6))

        # Room Buttons
        self.room_buttons: Dict[str, ttk.Button] = {}
        for room_name in ClinicalRoom.all_rooms():
            def make_handler(r: str) -> Any:
                return lambda: self.on_switch_room(r)

            btn = ttk.Button(
                self.sidebar_frame,
                text=f"📂 {room_name}",
                style="Room.TButton",
                command=make_handler(room_name),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.room_buttons[room_name] = btn

        # Separator
        ttk.Separator(self.sidebar_frame, orient="horizontal").pack(fill="x", padx=10, pady=14)

        # Active Staff List Title
        tk.Label(
            self.sidebar_frame,
            text="ACTIVE IN ROOM",
            font=("Segoe UI", 9, "bold"),
            bg=BG_SIDEBAR,
            fg=TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(0, 6))

        # User Listbox
        self.user_listbox = tk.Listbox(
            self.sidebar_frame,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            highlightthickness=0,
            borderwidth=0,
            selectbackground="#374151",
            font=("Segoe UI", 10),
        )
        self.user_listbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # --- Central Chat Display & Input Bar ---
        self.chat_frame = tk.Frame(self.main_container, bg=BG_DARK)
        self.chat_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        # Message History Text
        self.msg_display = tk.Text(
            self.chat_frame,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 10),
            wrap="word",
            state="disabled",
            borderwidth=0,
            padx=12,
            pady=12,
        )
        self.msg_display.pack(fill="both", expand=True)

        # Tags formatting
        self.msg_display.tag_configure("DOCTOR", foreground=ACCENT_CYAN, font=("Segoe UI", 10, "bold"))
        self.msg_display.tag_configure("NURSE", foreground=ACCENT_GREEN, font=("Segoe UI", 10, "bold"))
        self.msg_display.tag_configure("ADMIN", foreground=ACCENT_AMBER, font=("Segoe UI", 10, "bold"))
        self.msg_display.tag_configure("SYSTEM", foreground=TEXT_MUTED, font=("Segoe UI", 9, "italic"))
        self.msg_display.tag_configure("TIMESTAMP", foreground="#6b7280", font=("Segoe UI", 8))
        self.msg_display.tag_configure("TEXT", foreground=TEXT_PRIMARY)
        self.msg_display.tag_configure("ERROR", foreground=ACCENT_RED, font=("Segoe UI", 10, "bold"))

        # Message Input Entry Bar
        self.input_frame = tk.Frame(self.chat_frame, bg=BG_DARK)
        self.input_frame.pack(side="bottom", fill="x", pady=(8, 0))

        self.msg_entry = tk.Entry(
            self.input_frame,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            font=("Segoe UI", 11),
            borderwidth=0,
        )
        self.msg_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 6))
        self.msg_entry.bind("<Return>", lambda e: self.on_send_message())

        self.send_button = ttk.Button(
            self.input_frame,
            text="Send 📨",
            command=self.on_send_message,
        )
        self.send_button.pack(side="right")

        # Bottom Status Notification Bar
        self.status_bar = tk.Label(
            self,
            text="Ready. Please login or register to participate in clinical conversations.",
            bg=BG_SIDEBAR,
            fg=TEXT_MUTED,
            anchor="w",
            padx=14,
            pady=4,
            font=("Segoe UI", 9),
        )
        self.status_bar.pack(side="bottom", fill="x")

        # Prompt Login Dialog on Startup
        self.after(200, self.show_auth_dialog)

    # ---------------- AUTHENTICATION DIALOG ----------------

    def show_auth_dialog(self) -> None:
        """Display modal authentication and registration window."""
        dialog = tk.Toplevel(self)
        dialog.title("ClinicFlow AI — Authentication")
        dialog.geometry("380x360")
        dialog.resizable(False, False)
        dialog.configure(bg=BG_CARD)
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(
            dialog,
            text="🔐 Clinical Staff Access",
            font=("Segoe UI", 14, "bold"),
            bg=BG_CARD,
            fg=ACCENT_CYAN,
        ).pack(pady=(16, 12))

        # Fields Frame
        form = tk.Frame(dialog, bg=BG_CARD)
        form.pack(padx=24, pady=8, fill="x")

        # Username
        tk.Label(form, text="Staff ID / Username:", bg=BG_CARD, fg=TEXT_MUTED, anchor="w").pack(fill="x")
        entry_user = tk.Entry(form, bg=BG_INPUT, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, font=("Segoe UI", 10))
        entry_user.pack(fill="x", pady=(2, 8), ipady=4)
        entry_user.insert(0, "dr_smith")

        # Password
        tk.Label(form, text="Password:", bg=BG_CARD, fg=TEXT_MUTED, anchor="w").pack(fill="x")
        entry_pass = tk.Entry(form, bg=BG_INPUT, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, show="•", font=("Segoe UI", 10))
        entry_pass.pack(fill="x", pady=(2, 8), ipady=4)
        entry_pass.insert(0, "HospitalPass123!")

        # Role
        tk.Label(form, text="Medical Role:", bg=BG_CARD, fg=TEXT_MUTED, anchor="w").pack(fill="x")
        role_combo = ttk.Combobox(form, values=["DOCTOR", "NURSE", "ADMIN"], state="readonly")
        role_combo.set("DOCTOR")
        role_combo.pack(fill="x", pady=(2, 16))

        # Action Buttons Frame
        btn_frame = tk.Frame(dialog, bg=BG_CARD)
        btn_frame.pack(fill="x", padx=24, pady=8)

        def do_login() -> None:
            user = entry_user.get().strip()
            pw = entry_pass.get().strip()
            if not user or not pw:
                messagebox.showerror("Validation", "Username and password required.", parent=dialog)
                return
            self._execute_connect_and_login(user, pw, dialog)

        def do_register() -> None:
            user = entry_user.get().strip()
            pw = entry_pass.get().strip()
            role = role_combo.get()
            if not user or not pw:
                messagebox.showerror("Validation", "Username and password required.", parent=dialog)
                return
            self._execute_connect_and_register(user, pw, role, dialog)

        ttk.Button(btn_frame, text="Login 🔑", command=do_login).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(btn_frame, text="Register ➕", command=do_register).pack(side="right", expand=True, fill="x", padx=(4, 0))

    def _execute_connect_and_login(self, user: str, pw: str, dialog: tk.Toplevel) -> None:
        """Connect to TCP server if needed and send LOGIN packet."""
        if not self.chat_client.is_connected:
            ok, msg = self.chat_client.connect(self.default_host, self.default_port)
            if not ok:
                messagebox.showerror("Connection Error", msg, parent=dialog)
                return

        self.chat_client.login(user, pw)
        self.set_status(f"Authenticating staff member '{user}'...")
        dialog.destroy()

    def _execute_connect_and_register(self, user: str, pw: str, role: str, dialog: tk.Toplevel) -> None:
        """Connect to TCP server and send REGISTER packet."""
        if not self.chat_client.is_connected:
            ok, msg = self.chat_client.connect(self.default_host, self.default_port)
            if not ok:
                messagebox.showerror("Connection Error", msg, parent=dialog)
                return

        self.chat_client.register(user, pw, role)
        self.set_status(f"Registering staff member '{user}' as {role}...")
        dialog.destroy()

    # ---------------- INTERACTION HANDLERS ----------------

    def on_send_message(self) -> None:
        """Transmit message to current room."""
        text = self.msg_entry.get().strip()
        if not text:
            return

        if not self.chat_client.is_authenticated:
            self.set_status("Authentication required to send clinical messages.", is_error=True)
            self.show_auth_dialog()
            return

        self.chat_client.send_chat_message(text)
        self.msg_entry.delete(0, "end")

    def on_switch_room(self, target_room: str) -> None:
        """Request room switch."""
        if target_room == self.chat_client.current_room:
            return

        if not self.chat_client.is_authenticated:
            self.set_status("Please authenticate before switching rooms.", is_error=True)
            self.show_auth_dialog()
            return

        self.set_status(f"Requesting transition to {target_room}...")
        self.chat_client.join_room(target_room)

    def set_status(self, message: str, is_error: bool = False) -> None:
        """Update bottom notification bar."""
        color = ACCENT_RED if is_error else TEXT_MUTED
        self.status_bar.configure(text=message, fg=color)

    # ---------------- PACKET RECEIVER QUEUE PIPELINE ----------------

    def _on_packet_received(self, packet: Packet) -> None:
        """Callback invoked from background receiver thread: enqueue packet."""
        self._packet_queue.put(packet)

    def _on_connection_lost(self, reason: str) -> None:
        """Callback invoked when socket terminates."""
        self.after(0, lambda: self._handle_disconnect(reason))

    def _process_packet_queue(self) -> None:
        """Process incoming queued packets safely on the Tkinter main thread."""
        while not self._packet_queue.empty():
            try:
                packet = self._packet_queue.get_nowait()
                self._dispatch_incoming_packet(packet)
            except queue.Empty:
                break
        self.after(50, self._process_packet_queue)

    def _dispatch_incoming_packet(self, packet: Packet) -> None:
        """Handle incoming packets on the main GUI thread."""
        p_type = packet.type

        if p_type == MessageType.AUTH_SUCCESS.value:
            payload = packet.payload if isinstance(packet.payload, dict) else {}
            username = str(payload.get("username", ""))
            role = str(payload.get("role", "NURSE"))
            room = str(payload.get("current_room", "#general"))

            self.user_badge.configure(text=f"[{role}] {username}", fg=ACCENT_CYAN if role == "DOCTOR" else ACCENT_GREEN)
            self.room_badge.configure(text=f"Room: {room}")
            self.set_status(f"Successfully logged in as [{role}] {username}.")
            self._append_system_msg(f"Welcome, {role} {username}. You are in {room}.")

        elif p_type == MessageType.JOIN_ROOM.value:
            payload = packet.payload if isinstance(packet.payload, dict) else {}
            room = str(payload.get("room", packet.room))
            self.room_badge.configure(text=f"Room: {room}")
            self.set_status(f"Switched active room to {room}.")
            self._clear_messages()
            self._append_system_msg(f"Switched to {room}.")

        elif p_type == MessageType.MSG_BROADCAST.value:
            payload = packet.payload if isinstance(packet.payload, dict) else {}
            text = str(payload.get("text", ""))
            self._append_chat_msg(packet.timestamp, packet.role, packet.sender, text)
            self.set_status(f"New message from [{packet.role}] {packet.sender} in {packet.room}")

        elif p_type == MessageType.SYSTEM_EVENT.value:
            payload = packet.payload if isinstance(packet.payload, dict) else {}
            msg = str(payload.get("message", ""))
            self._append_system_msg(msg)
            self.set_status(msg)

        elif p_type == MessageType.HISTORY_RESP.value:
            payload = packet.payload if isinstance(packet.payload, dict) else {}
            messages = payload.get("messages", [])
            if isinstance(messages, list):
                for m in messages:
                    if isinstance(m, dict):
                        self._append_chat_msg(
                            str(m.get("timestamp", "")),
                            str(m.get("role", "NURSE")),
                            str(m.get("sender", "")),
                            str(m.get("message", "")),
                        )

        elif p_type == MessageType.USER_LIST.value:
            payload = packet.payload if isinstance(packet.payload, dict) else {}
            users = payload.get("users", [])
            self._update_user_list(users)

        elif p_type == MessageType.ERROR.value:
            payload = packet.payload if isinstance(packet.payload, dict) else {}
            err = str(payload.get("error", "An error occurred."))
            self._append_error_msg(err)
            self.set_status(f"Error: {err}", is_error=True)

    def _append_chat_msg(self, timestamp: str, role: str, sender: str, text: str) -> None:
        """Format and append chat message to history display."""
        self.msg_display.configure(state="normal")
        time_part = timestamp[11:19] if len(timestamp) >= 19 else timestamp
        self.msg_display.insert("end", f"[{time_part}] ", "TIMESTAMP")
        self.msg_display.insert("end", f"[{role}] ", role if role in ("DOCTOR", "NURSE", "ADMIN") else "SYSTEM")
        self.msg_display.insert("end", f"{sender}: ", "TEXT")
        self.msg_display.insert("end", f"{text}\n", "TEXT")
        self.msg_display.configure(state="disabled")
        self.msg_display.see("end")

    def _append_system_msg(self, message: str) -> None:
        self.msg_display.configure(state="normal")
        self.msg_display.insert("end", f"ℹ️ {message}\n", "SYSTEM")
        self.msg_display.configure(state="disabled")
        self.msg_display.see("end")

    def _append_error_msg(self, error: str) -> None:
        self.msg_display.configure(state="normal")
        self.msg_display.insert("end", f"⚠️ Error: {error}\n", "ERROR")
        self.msg_display.configure(state="disabled")
        self.msg_display.see("end")

    def _clear_messages(self) -> None:
        self.msg_display.configure(state="normal")
        self.msg_display.delete("1.0", "end")
        self.msg_display.configure(state="disabled")

    def _update_user_list(self, users: Any) -> None:
        self.user_listbox.delete(0, "end")
        if isinstance(users, list):
            for u in users:
                if isinstance(u, dict):
                    name = u.get("username", "Unknown")
                    role = u.get("role", "NURSE")
                    self.user_listbox.insert("end", f"• [{role}] {name}")

    def _handle_disconnect(self, reason: str) -> None:
        self.user_badge.configure(text="[DISCONNECTED]", fg=ACCENT_RED)
        self.set_status(f"Disconnected: {reason}", is_error=True)
        self._append_error_msg("Disconnected from server.")

    def on_close(self) -> None:
        """Handle window exit cleanly."""
        self.chat_client.disconnect()
        self.destroy()
