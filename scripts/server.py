#!/usr/bin/env python3
"""
Simple HTTP server for Siri Shortcuts integration.
Runs on Mac and can be called from iOS/iPadOS via HTTP request.

Start: python scripts/server.py
Or: make server
"""

from __future__ import annotations

import argparse
import logging
import os
import ssl
import threading
import time
from pathlib import Path

from homeconnect_coffee.api_monitor import get_monitor
from homeconnect_coffee.errors import ErrorHandler
from homeconnect_coffee.handlers import RequestRouter
from homeconnect_coffee.handlers.dashboard_handler import DashboardHandler
from homeconnect_coffee.handlers.history_handler import HistoryHandler
from homeconnect_coffee.history import HistoryManager
from homeconnect_coffee.services import EventStreamManager


# Global variables (initialized in main())
history_manager: HistoryManager | None = None
event_stream_manager: EventStreamManager | None = None
error_handler: ErrorHandler | None = None

# Logger for server
logger = logging.getLogger(__name__)






def main() -> None:
    global history_manager, event_stream_manager, error_handler

    parser = argparse.ArgumentParser(description="HTTP server for Siri Shortcuts integration")
    parser.add_argument("--port", type=int, default=8080, help="Port for HTTP server (default: 8080)")
    parser.add_argument("--host", type=str, default="localhost", help="Host (default: localhost)")
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Disable request logging",
    )
    parser.add_argument(
        "--api-token",
        type=str,
        default=None,
        help="API token for authentication (or set COFFEE_API_TOKEN in .env)",
    )
    parser.add_argument(
        "--cert",
        type=str,
        default=None,
        help="Path to SSL certificate (for HTTPS). Also requires --key.",
    )
    parser.add_argument(
        "--key",
        type=str,
        default=None,
        help="Path to SSL private key (for HTTPS). Also requires --cert.",
    )
    args = parser.parse_args()

    # Initialize error handler
    log_sensitive = os.getenv("LOG_SENSITIVE", "false").lower() == "true"
    error_handler = ErrorHandler(
        enable_logging=not args.no_log,
        log_sensitive=log_sensitive,
    )

    # API token from argument or environment variable
    api_token = args.api_token or os.getenv("COFFEE_API_TOKEN")

    # Initialize history manager
    history_path = Path(__file__).parent.parent / "history.json"
    history_manager = HistoryManager(history_path)

    # Initialize event stream manager
    event_stream_manager = EventStreamManager(
        history_manager=history_manager,
        enable_logging=not args.no_log,
    )

    # Set global variables for handlers (for static methods)
    from homeconnect_coffee.handlers.dashboard_handler import event_stream_manager as dashboard_event_manager
    from homeconnect_coffee.handlers.history_handler import history_manager as history_handler_manager
    
    # Set global variables in handler modules
    import homeconnect_coffee.handlers.dashboard_handler as dashboard_module
    import homeconnect_coffee.handlers.history_handler as history_module
    dashboard_module.event_stream_manager = event_stream_manager
    history_module.history_manager = history_manager

    # Initialize API call monitor
    stats_path = Path(__file__).parent.parent / "api_stats.json"
    monitor = get_monitor(stats_path)
    monitor.print_stats()  # Show current statistics on startup

    # Initialize auth middleware
    from homeconnect_coffee.middleware import AuthMiddleware
    auth_middleware = AuthMiddleware(api_token=api_token, error_handler=error_handler)
    
    # Configure router
    RequestRouter.enable_logging = not args.no_log
    RequestRouter.api_token = api_token  # For legacy compatibility
    RequestRouter.error_handler = error_handler
    RequestRouter.auth_middleware = auth_middleware

    # Use ThreadingHTTPServer so multiple requests can be processed simultaneously
    from http.server import ThreadingHTTPServer
    server = ThreadingHTTPServer((args.host, args.port), RequestRouter)

    # Enable HTTPS if certificate and key are provided
    protocol = "http"
    if args.cert and args.key:
        if not Path(args.cert).exists():
            raise FileNotFoundError(f"Certificate not found: {args.cert}")
        if not Path(args.key).exists():
            raise FileNotFoundError(f"Private key not found: {args.key}")

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert, args.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        protocol = "https"

    print(f"☕ HomeConnect Coffee Server running on {protocol}://{args.host}:{args.port}")
    print(f"   Endpoints:")
    print(f"   - GET  /cert        - Download SSL certificate (public)")
    print(f"   - GET  /dashboard   - Dashboard UI (public)")
    print(f"   - GET  /wake        - Activates the device")
    print(f"   - GET  /status      - Shows the status")
    print(f"   - GET  /api/status  - Extended status (Settings, Programs)")
    print(f"   - GET  /api/history - History data (public)")
    print(f"   - GET  /api/stats   - API call statistics (public)")
    print(f"   - GET  /events      - Live events stream (SSE)")
    print(f"   - POST /brew        - Starts an espresso (JSON: {{\"fill_ml\": 50}})")
    if RequestRouter.enable_logging:
        print(f"   - Logging: enabled")
    else:
        print(f"   - Logging: disabled")
    if RequestRouter.api_token:
        print(f"   - Authentication: enabled")
        print(f"   - Use token: Header 'Authorization: Bearer TOKEN' or ?token=TOKEN")
    else:
        print(f"   - Authentication: disabled (server is open!)")
    print(f"\n   Press Ctrl+C to stop")
    
    # Start event stream manager (AFTER server start, so server doesn't block)
    # Worker runs ALWAYS to collect events for history
    # Only sends events to connected clients (saves resources)
    def start_event_manager_delayed():
        time.sleep(2)  # Wait 2 seconds for server to fully start
        if event_stream_manager:
            event_stream_manager.start()
    
    manager_starter = threading.Thread(target=start_event_manager_delayed, daemon=True)
    manager_starter.start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        if event_stream_manager:
            event_stream_manager.stop()
        server.shutdown()


if __name__ == "__main__":
    main()

