#!/usr/bin/env python3
"""
Einfacher HTTP-Server für Siri Shortcuts Integration.
Läuft auf dem Mac und kann von iOS/iPadOS per HTTP-Request aufgerufen werden.

Start: python scripts/server.py
Oder: make server
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode

import requests

from homeconnect_coffee.api_monitor import get_monitor
from homeconnect_coffee.client import HomeConnectClient
from homeconnect_coffee.config import load_config
from homeconnect_coffee.history import HistoryManager
from homeconnect_coffee.services import (
    CoffeeService,
    EventStreamManager,
    HistoryService,
    StatusService,
)


# Globale Variablen (werden in main() initialisiert)
history_manager: HistoryManager | None = None
event_stream_manager: EventStreamManager | None = None


class CoffeeHandler(BaseHTTPRequestHandler):
    enable_logging = True
    api_token: str | None = None

    def handle_one_request(self):
        """Überschreibt handle_one_request, um BrokenPipeError abzufangen."""
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client hat Verbindung geschlossen - normal, nicht loggen
            pass

    def log_request(self, code="-", size="-"):
        """Loggt Requests wenn Logging aktiviert ist."""
        if self.enable_logging:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            client_ip = self.client_address[0]
            method = self.command
            path = self._mask_token_in_path(self.path)
            print(f"[{timestamp}] {client_ip} - {method} {path} - {code}")

    def _mask_token_in_path(self, path: str) -> str:
        """Maskiert Token-Parameter im Pfad für das Logging."""
        if "token=" not in path:
            return path
        
        parsed = urlparse(path)
        query_params = parse_qs(parsed.query)
        
        if "token" in query_params:
            # Maskiere Token
            query_params["token"] = ["__MASKED__"]
            new_query = urlencode(query_params, doseq=True)
            return f"{parsed.path}?{new_query}"
        
        return path

    def _check_auth(self) -> bool:
        """Prüft die Authentifizierung via Header oder Query-Parameter."""
        if self.api_token is None:
            return True  # Kein Token konfiguriert = offen

        # Prüfe Authorization Header
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token == self.api_token:
                return True

        # Prüfe Query-Parameter
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        token_param = query_params.get("token", [None])[0]
        if token_param == self.api_token:
            return True

        return False

    def log_message(self, format, *args):
        """Unterdrückt Standard-Logging-Nachrichten (nur log_request wird verwendet)."""
        # Wir verwenden nur log_request für Request-Logging
        pass

    def do_GET(self):
        """Behandelt GET-Requests für Wake und Status."""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path

            # Öffentliche Endpoints (keine Authentifizierung) - ZUERST prüfen!
            # Diese Endpoints erstellen KEINEN Client und blockieren nicht
            if path == "/cert":
                self._handle_cert_download()
                return
            elif path == "/health":
                self._send_json({"status": "ok"}, status_code=200)
                return
            elif path == "/dashboard":
                self._handle_dashboard()
                return
            elif path == "/api/history":
                # History-Endpoint - öffentlich (nur Lesen)
                self._handle_history()
                return
            elif path == "/api/stats":
                # API-Statistiken - öffentlich (nur Lesen)
                self._handle_api_stats()
                return
            elif path == "/events":
                # Events-Stream benötigt keinen Client - der Worker liefert die Events
                # Öffentlich, da der Worker bereits authentifiziert ist
                self._handle_events_stream()
                return

            # Prüfe Authentifizierung für alle anderen Endpoints
            if not self._check_auth():
                self._send_error(401, "Unauthorized - Invalid or missing API token")
                return

            # Config und Client-Erstellung
            try:
                config = load_config()
                client = HomeConnectClient(config)
            except Exception as e:
                if CoffeeHandler.enable_logging:
                    print(f"Fehler beim Laden der Config/Client: {e}")
                self._send_error(500, f"Fehler beim Initialisieren: {str(e)}")
                return

            if path == "/wake":
                self._handle_wake(client)
            elif path == "/status":
                self._handle_status(client)
            elif path == "/api/status":
                self._handle_extended_status(client)
            elif path == "/brew":
                # Brew auch als GET unterstützen (mit Query-Parameter fill_ml)
                parsed_path = urlparse(self.path)
                query_params = parse_qs(parsed_path.query)
                fill_ml_param = query_params.get("fill_ml", [None])[0]
                fill_ml = int(fill_ml_param) if fill_ml_param and fill_ml_param.isdigit() else 50
                self._handle_brew(client, fill_ml)
            else:
                self._send_error(404, "Not Found")

        except Exception as e:
            if CoffeeHandler.enable_logging:
                print(f"Fehler in do_GET: {e}")
            self._send_error(500, str(e))

    def do_POST(self):
        """Behandelt POST-Requests für Brew."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Prüfe Authentifizierung
        if not self._check_auth():
            self._send_error(401, "Unauthorized - Invalid or missing API token")
            return

        try:
            # Config und Client-Erstellung
            try:
                config = load_config()
                client = HomeConnectClient(config)
            except Exception as e:
                if CoffeeHandler.enable_logging:
                    print(f"Fehler beim Laden der Config/Client: {e}")
                self._send_error(500, f"Fehler beim Initialisieren: {str(e)}")
                return

            if path == "/brew":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                data = json.loads(body) if body else {}
                fill_ml = data.get("fill_ml", 50)
                self._handle_brew(client, fill_ml)
            else:
                self._send_error(404, "Not Found")

        except Exception as e:
            if CoffeeHandler.enable_logging:
                print(f"Fehler in do_POST: {e}")
            self._send_error(500, str(e))

    def _handle_wake(self, client: HomeConnectClient) -> None:
        """Aktiviert das Gerät aus dem Standby."""
        try:
            coffee_service = CoffeeService(client)
            result = coffee_service.wake_device()
            self._send_json(result, status_code=200)
        except requests.exceptions.Timeout:
            self._send_error(504, "API-Anfrage hat das Timeout überschritten")
        except Exception as e:
            self._send_error(500, f"Fehler beim Aktivieren: {str(e)}")

    def _handle_status(self, client: HomeConnectClient) -> None:
        """Gibt den Gerätestatus zurück."""
        status_service = StatusService(client)
        status = status_service.get_status()
        self._send_json(status, status_code=200)

    def _handle_extended_status(self, client: HomeConnectClient) -> None:
        """Gibt erweiterten Status mit Settings und Programmen zurück."""
        try:
            status_service = StatusService(client)
            extended_status = status_service.get_extended_status()
            self._send_json(extended_status, status_code=200)
        except Exception as e:
            self._send_error(500, str(e))

    def _handle_dashboard(self) -> None:
        """Liefert die Dashboard-HTML-Seite."""
        dashboard_path = Path(__file__).parent / "dashboard.html"
        
        if not dashboard_path.exists():
            self._send_error(404, "Dashboard nicht gefunden")
            return
        
        try:
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(dashboard_html.encode("utf-8"))
        except Exception as e:
            self._send_error(500, f"Fehler beim Lesen des Dashboards: {str(e)}")

    def _handle_history(self) -> None:
        """Gibt die Verlaufsdaten zurück."""
        if history_manager is None:
            self._send_error(500, "History-Manager nicht initialisiert")
            return
        
        try:
            history_service = HistoryService(history_manager)
            
            # Parse Query-Parameter
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            
            event_type = query_params.get("type", [None])[0]
            limit = query_params.get("limit", [None])[0]
            # Begrenze Limit auf maximal 1000, um Server-Überlastung zu vermeiden
            limit_int = min(int(limit), 1000) if limit and limit.isdigit() else None
            
            # Cursor-basierte Pagination: before_timestamp
            before_timestamp = query_params.get("before_timestamp", [None])[0]
            
            if query_params.get("daily_usage"):
                # Tägliche Nutzung
                days = min(int(query_params.get("days", ["7"])[0]), 365)  # Max 1 Jahr
                usage = history_service.get_daily_usage(days)
                self._send_json({"daily_usage": usage}, status_code=200)
            elif query_params.get("program_counts"):
                # Programm-Zählungen
                counts = history_service.get_program_counts()
                self._send_json({"program_counts": counts}, status_code=200)
            else:
                # Standard-History
                history = history_service.get_history(event_type, limit_int, before_timestamp)
                self._send_json({"history": history}, status_code=200)
        except ValueError as e:
            self._send_error(400, f"Ungültiger Parameter: {str(e)}")
        except Exception as e:
            if CoffeeHandler.enable_logging:
                print(f"Fehler beim Laden der History: {e}")
            self._send_error(500, "Fehler beim Laden der History")

    def _handle_api_stats(self) -> None:
        """Gibt die API-Call-Statistiken zurück."""
        try:
            stats_path = Path(__file__).parent.parent / "api_stats.json"
            monitor = get_monitor(stats_path)
            stats = monitor.get_stats()
            self._send_json(stats, status_code=200)
        except Exception as e:
            if CoffeeHandler.enable_logging:
                print(f"Fehler beim Laden der API-Statistiken: {e}")
            self._send_error(500, "Fehler beim Laden der API-Statistiken")

    def _handle_cert_download(self) -> None:
        """Stellt das SSL-Zertifikat zum Download bereit."""
        cert_path = Path(__file__).parent.parent / "certs" / "server.crt"
        
        if not cert_path.exists():
            self._send_error(404, "Zertifikat nicht gefunden. Bitte erst 'make cert' ausführen.")
            return
        
        try:
            cert_data = cert_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-x509-ca-cert")
            self.send_header("Content-Disposition", 'attachment; filename="HomeConnectCoffee.crt"')
            self.send_header("Content-Length", str(len(cert_data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(cert_data)
            # log_request wird automatisch von BaseHTTPRequestHandler aufgerufen
        except Exception as e:
            self._send_error(500, f"Fehler beim Lesen des Zertifikats: {str(e)}")

    def _handle_events_stream(self) -> None:
        """Handhabt Server-Sent Events Stream für Live-Updates.
        
        Erstellt KEINEN Client, um Blockierungen zu vermeiden.
        Der Event-Stream-Worker liefert die Events im Hintergrund.
        """
        global event_stream_manager
        
        if event_stream_manager is None:
            self._send_error(500, "Event-Stream-Manager nicht initialisiert")
            return
        
        # SSE-Header senden
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Client zum Manager hinzufügen
        event_stream_manager.add_client(self)

        try:
            # Sende initiales Event
            self._send_sse_event("connected", {"message": "Verbunden"})

            # Halte Verbindung offen und sende Keep-Alive
            while True:
                time.sleep(30)
                self._send_sse_event("ping", {"timestamp": datetime.now().isoformat()})
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client hat Verbindung geschlossen
            pass
        finally:
            # Client aus Manager entfernen
            event_stream_manager.remove_client(self)

    def _send_sse_event(self, event_type: str, data: dict) -> None:
        """Sendet ein SSE-Event."""
        try:
            event_str = f"event: {event_type}\n"
            event_str += f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            self.wfile.write(event_str.encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client hat Verbindung geschlossen
            raise

    def _handle_brew(self, client: HomeConnectClient, fill_ml: int) -> None:
        """Startet einen Espresso."""
        try:
            coffee_service = CoffeeService(client)
            result = coffee_service.brew_espresso(fill_ml)
            self._send_json(result, status_code=200)
        except Exception as e:
            if CoffeeHandler.enable_logging:
                print(f"Fehler beim Starten des Programms: {e}")
            self._send_error(500, f"Fehler beim Starten des Programms: {str(e)}")

    def _send_json(self, data: dict, status_code: int = 200) -> None:
        """Sendet eine JSON-Response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        response_body = json.dumps(data, indent=2).encode("utf-8")
        self.wfile.write(response_body)
        # log_request wird automatisch von BaseHTTPRequestHandler aufgerufen

    def _send_error(self, code: int, message: str) -> None:
        """Sendet eine Fehler-Response."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        error_body = json.dumps({"error": message}).encode("utf-8")
        self.wfile.write(error_body)
        # log_request wird automatisch von BaseHTTPRequestHandler aufgerufen

    def log_message(self, format, *args):
        """Unterdrückt Standard-Logging."""
        pass




def main() -> None:
    global history_manager, event_stream_manager

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

    CoffeeHandler.enable_logging = not args.no_log

    # API-Token aus Argument oder Umgebungsvariable
    api_token = args.api_token or os.getenv("COFFEE_API_TOKEN")
    CoffeeHandler.api_token = api_token

    # History-Manager initialisieren
    history_path = Path(__file__).parent.parent / "history.json"
    history_manager = HistoryManager(history_path)

    # Event-Stream-Manager initialisieren
    event_stream_manager = EventStreamManager(
        history_manager=history_manager,
        enable_logging=CoffeeHandler.enable_logging,
    )

    # API-Call-Monitor initialisieren
    stats_path = Path(__file__).parent.parent / "api_stats.json"
    monitor = get_monitor(stats_path)
    monitor.print_stats()  # Zeige aktuelle Statistiken beim Start

    # ThreadingHTTPServer verwenden, damit mehrere Requests gleichzeitig verarbeitet werden können
    from http.server import ThreadingHTTPServer
    server = ThreadingHTTPServer((args.host, args.port), CoffeeHandler)

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
    if CoffeeHandler.enable_logging:
        print(f"   - Logging: aktiviert")
    else:
        print(f"   - Logging: deaktiviert")
    if CoffeeHandler.api_token:
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

