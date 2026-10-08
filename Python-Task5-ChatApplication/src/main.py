"""Main application entrypoint for ClinicFlow AI Secure Clinical Messaging Hub."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from typing import Any

from src.client.cli import run_cli_client
from src.client.gui import ClinicalChatGUI
from src.server.server import ClinicalChatServer

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ClinicFlowMain")


def main() -> None:
    """CLI launcher for Server, GUI Client, or CLI Client."""
    parser = argparse.ArgumentParser(description="ClinicFlow AI Secure Clinical Messaging Hub")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--server", action="store_true", help="Launch TCP socket server")
    group.add_argument("--gui", action="store_true", help="Launch Tkinter desktop GUI client (default)")
    group.add_argument("--cli", action="store_true", help="Launch terminal CLI client")

    parser.add_argument("--host", type=str, default="127.0.0.1", help="Target host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8443, help="Target port (default: 8443)")
    parser.add_argument("--db", type=str, default="clinical_chat.db", help="SQLite database path (server only)")

    args = parser.parse_args()

    if args.server:
        logger.info("Starting ClinicFlow TCP Server on %s:%d...", args.host, args.port)
        from src.server.db import DatabaseManager
        db_mgr = DatabaseManager(db_path=args.db)
        server = ClinicalChatServer(host=args.host, port=args.port, db_manager=db_mgr)
        server.start()

        def sig_handler(signum: int, frame: Any) -> None:
            print("\nShutting down ClinicFlow server...")
            server.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, sig_handler)
        print(f"ClinicFlow Server running on {args.host}:{server.port}. Press Ctrl+C to terminate.")
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break
        server.stop()

    elif args.cli:
        run_cli_client(host=args.host, port=args.port)

    else:
        # Default: Desktop GUI Client
        logger.info("Launching ClinicFlow Desktop GUI Client...")
        app = ClinicalChatGUI(default_host=args.host, default_port=args.port)
        app.mainloop()


if __name__ == "__main__":
    main()
