# ClinicFlow AI Secure Clinical Messaging Hub (Oasis Infobyte Task 5)

An Advanced-tier, standalone multi-client TCP messaging hub engineered for secure medical staff communication. Developed as part of the Oasis Infobyte Internship Program, this application features **binary length-prefixed JSON socket framing**, **PBKDF2-HMAC-SHA256 user authentication with per-user cryptographic salts**, **departmental room segregation**, **role-based access control**, **SQLite persistent message replay and audit logging**, and a **modern dark-mode desktop GUI**.

---

## 🎯 Architecture Overview

```
Python-Task5-ChatApplication/
├── src/
│   ├── protocol/
│   │   ├── schemas.py             # Typed dataclass schemas (packet_id, type, role, room, payload)
│   │   └── serializer.py          # 4-byte length-prefixed binary framing engine
│   ├── server/
│   │   ├── db.py                  # SQLite audit logging, replay store, PBKDF2 salt/hashing
│   │   ├── connection_manager.py  # Thread-safe client session, room, and role manager
│   │   └── server.py              # Concurrent multi-client TCP socket server
│   ├── client/
│   │   ├── client.py              # Dual-threaded socket client engine
│   │   ├── gui.py                 # Modern Tkinter desktop GUI client
│   │   └── cli.py                 # Lightweight terminal CLI client
│   └── main.py                    # Multi-mode CLI launcher (--server, --gui, --cli)
├── tests/
│   ├── test_protocol.py           # Framing, schema validation, and Unicode transit tests
│   ├── test_security_db.py        # PBKDF2 verification, per-user salt isolation, replay tests
│   └── test_server.py             # Room segregation, role-based access, and cleanup tests
├── smoke_test.py                  # End-to-end multi-client runtime smoke test
├── requirements.txt               # Independent dependency manifest
└── README.md                      # Documentation & demo talking points
```

---

## 📡 Protocol Framing Specification

To eliminate TCP packet fragmentation, boundary truncation, and packet sticking issues over raw streams, ClinicFlow uses a 4-byte big-endian binary length header:

```
+------------------------------------+------------------------------------------+
| 4 Bytes: Big-Endian Unsigned Int   | N Bytes: UTF-8 Encoded JSON Payload      |
| struct.pack(">I", payload_length)  | json.dumps(packet.to_dict())             |
+------------------------------------+------------------------------------------+
```

### Packet Schema Structure
```json
{
  "packet_id": "a1b2c3d4",
  "type": "MSG_BROADCAST",
  "sender": "dr_watson",
  "role": "DOCTOR",
  "room": "#triage",
  "payload": {
    "text": "Patient vitals stabilized 🩺"
  },
  "timestamp": "2026-10-08T01:45:00.123456"
}
```

---

## 🔒 Security & Privacy Guarantees

1. **PBKDF2 Password Hashing**: Passwords are never stored in plaintext or unsalted hashes. Hashes are derived using `hashlib.pbkdf2_hmac("sha256", password, salt, 100000)`.
2. **Cryptographic Per-User Salts**: Each registered user receives a unique 16-byte random salt generated via `os.urandom(16)`. Identical passwords produce distinct cryptographic hashes.
3. **Zero Secret Logging**: Passwords, salts, session tokens, and authentication payloads are strictly masked from logs and audit trails.
4. **Isolated SQLite Storage**: `clinical_chat.db` is automatically gitignored and excluded from version control.
5. **Role-Based Access Control (RBAC)**:
   - **`ADMIN`**: Full administrative oversight across all rooms.
   - **`DOCTOR`**: Access to `#physician-consult`, `#triage`, and `#general`.
   - **`NURSE`**: Access to `#triage` and `#general` (restricted from `#physician-consult`).
   - Unauthorized attempts return structured `ERROR` packets.

---

## ✨ Features & Oasis Infobyte Requirements

| Requirement | Implementation Details | Status |
| :--- | :--- | :---: |
| **Binary Length-Prefixed Framing** | 4-byte big-endian integer framing eliminating TCP fragmentation. Full Unicode and emoji support. | ✅ Complete |
| **Concurrent TCP Server** | Threaded multi-client listener with thread-safe session and room management. | ✅ Complete |
| **Departmental Room Segregation** | Strict broadcast isolation across `#triage`, `#physician-consult`, and `#general`. | ✅ Complete |
| **Role-Based Access Control** | Enforced permissions for `DOCTOR`, `NURSE`, and `ADMIN`. | ✅ Complete |
| **Secure PBKDF2 Authentication** | Per-user cryptographic salts and PBKDF2-HMAC-SHA256 (100k iterations). | ✅ Complete |
| **Message History & Replay** | Persistent SQLite store with automatic replay upon room joining. | ✅ Complete |
| **Audit Logging** | Complete SQLite audit trail of user registrations, logins, and room shifts. | ✅ Complete |
| **Tkinter Desktop GUI Client** | Python stdlib dark-mode GUI with auth dialog, room switcher, user list, and role badges. | ✅ Complete |
| **Terminal CLI Client** | Lightweight console client for headless debugging and scripting. | ✅ Complete |
| **Graceful Disconnects** | Clean socket and session termination on window close or `/exit`. | ✅ Complete |

---

## 🚀 Setup & Execution

### Tested Python Version
- **Python 3.11.9+** (Windows, Linux, macOS)

### 1. Installation
Navigate to the Task 5 directory:
```bash
cd D:\College\Resume\VW\OASIS\OIBSIP\Python-Task5-ChatApplication
pip install -r requirements.txt
```

### 2. Launching the TCP Server
```bash
python -m src.main --server --port 8443
```

### 3. Launching Desktop GUI Clients
In separate terminal windows, start the graphical client:
```bash
python -m src.main --gui --port 8443
```

### 4. Launching Terminal CLI Clients
```bash
python -m src.main --cli --port 8443
```

---

## 🧪 Automated Testing & Verification

### Running Pytest
```bash
pytest -v
```

### Running Static Type Checking (mypy)
```bash
mypy src
```

### Running the End-to-End Multi-Client Smoke Test
```bash
python smoke_test.py
```

---

