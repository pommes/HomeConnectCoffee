#!/usr/bin/env python3
"""
Einfacher HTTP-Server für Siri Shortcuts Integration.
Läuft auf dem Mac und kann von iOS/iPadOS per HTTP-Request aufgerufen werden.

Start: python scripts/server.py
Oder: make server
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


# Globale Variablen (werden in main() initialisiert)
history_manager: HistoryManager | None = None
event_stream_manager: EventStreamManager | None = None
error_handler: ErrorHandler | None = None

# Logger für Server
logger = logging.getLogger(__name__)






def main() -> None:
    global history_manager, event_stream_manager, error_handler

    parser = argparse.ArgumentParser(description="HTTP-Server für Siri Shortcuts Integration")
    parser.add_argument("--port", type=int, default=8080, help="Port für den HTTP-Server (Standard: 8080)")
    parser.add_argument("--host", type=str, default="localhost", help="Host (Standard: localhost)")
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Deaktiviert das Request-Logging",
    )
    parser.add_argument(
        "--api-token",
        type=str,
        default=None,
        help="API-Token für Authentifizierung (oder setze COFFEE_API_TOKEN in .env)",
    )
    parser.add_argument(
        "--cert",
        type=str,
        default=None,
        help="Pfad zum SSL-Zertifikat (für HTTPS). Benötigt auch --key.",
    )
    parser.add_argument(
        "--key",
        type=str,
        default=None,
        help="Pfad zum SSL-Private-Key (für HTTPS). Benötigt auch --cert.",
    )
    args = parser.parse_args()

    # Error-Handler initialisieren
    log_sensitive = os.getenv("LOG_SENSITIVE", "false").lower() == "true"
    error_handler = ErrorHandler(
        enable_logging=not args.no_log,
        log_sensitive=log_sensitive,
    )

    # API-Token aus Argument oder Umgebungsvariable
    api_token = args.api_token or os.getenv("COFFEE_API_TOKEN")

    # History-Manager initialisieren
    history_path = Path(__file__).parent.parent / "history.json"
    history_manager = HistoryManager(history_path)

    # Event-Stream-Manager initialisieren
    event_stream_manager = EventStreamManager(
        history_manager=history_manager,
        enable_logging=not args.no_log,
    )

    # Setze globale Variablen für Handler (für statische Methoden)
    from homeconnect_coffee.handlers.dashboard_handler import event_stream_manager as dashboard_event_manager
    from homeconnect_coffee.handlers.history_handler import history_manager as history_handler_manager
    
    # Setze globale Variablen in den Handler-Modulen
    import homeconnect_coffee.handlers.dashboard_handler as dashboard_module
    import homeconnect_coffee.handlers.history_handler as history_module
    dashboard_module.event_stream_manager = event_stream_manager
    history_module.history_manager = history_manager

    # API-Call-Monitor initialisieren
    stats_path = Path(__file__).parent.parent / "api_stats.json"
    monitor = get_monitor(stats_path)
    monitor.print_stats()  # Zeige aktuelle Statistiken beim Start

    # Router konfigurieren
    RequestRouter.enable_logging = not args.no_log
    RequestRouter.api_token = api_token
    RequestRouter.error_handler = error_handler

    # ThreadingHTTPServer verwenden, damit mehrere Requests gleichzeitig verarbeitet werden können
    from http.server import ThreadingHTTPServer
    server = ThreadingHTTPServer((args.host, args.port), RequestRouter)

    # HTTPS aktivieren, falls Zertifikat und Key angegeben
    protocol = "http"
    if args.cert and args.key:
        if not Path(args.cert).exists():
            raise FileNotFoundError(f"Zertifikat nicht gefunden: {args.cert}")
        if not Path(args.key).exists():
            raise FileNotFoundError(f"Private Key nicht gefunden: {args.key}")

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert, args.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        protocol = "https"

    print(f"☕ HomeConnect Coffee Server läuft auf {protocol}://{args.host}:{args.port}")
    print(f"   Endpoints:")
    print(f"   - GET  /cert        - Download SSL-Zertifikat (öffentlich)")
    print(f"   - GET  /dashboard   - Dashboard-UI (öffentlich)")
    print(f"   - GET  /wake        - Aktiviert das Gerät")
    print(f"   - GET  /status      - Zeigt den Status")
    print(f"   - GET  /api/status  - Erweiterter Status (Settings, Programme)")
    print(f"   - GET  /api/history - Verlaufsdaten (öffentlich)")
    print(f"   - GET  /api/stats   - API-Call-Statistiken (öffentlich)")
    print(f"   - GET  /events      - Live Events-Stream (SSE)")
    print(f"   - POST /brew        - Startet einen Espresso (JSON: {{\"fill_ml\": 50}})")
    if RequestRouter.enable_logging:
        print(f"   - Logging: aktiviert")
    else:
        print(f"   - Logging: deaktiviert")
    if RequestRouter.api_token:
        print(f"   - Authentifizierung: aktiviert")
        print(f"   - Token verwenden: Header 'Authorization: Bearer TOKEN' oder ?token=TOKEN")
    else:
        print(f"   - Authentifizierung: deaktiviert (Server ist offen!)")
    print(f"\n   Drücke Ctrl+C zum Beenden")
    
    # Events-Stream Manager starten (NACH Server-Start, damit Server nicht blockiert)
    # Worker läuft IMMER, um Events für die History zu sammeln
    # Sendet Events nur an verbundene Clients (spart Ressourcen)
    def start_event_manager_delayed():
        time.sleep(2)  # Warte 2 Sekunden, damit Server vollständig gestartet ist
        if event_stream_manager:
            event_stream_manager.start()
    
    manager_starter = threading.Thread(target=start_event_manager_delayed, daemon=True)
    manager_starter.start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer wird beendet...")
        if event_stream_manager:
            event_stream_manager.stop()
        server.shutdown()


if __name__ == "__main__":
    main()

