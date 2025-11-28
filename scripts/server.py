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
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from queue import Queue
from threading import Lock
from urllib.parse import urlparse, parse_qs, urlencode

import requests
from sseclient import SSEClient

from homeconnect_coffee.client import HomeConnectClient
from homeconnect_coffee.config import load_config
from homeconnect_coffee.history import HistoryManager


# Globale Variablen für Events-Stream
EVENTS_URL = "https://api.home-connect.com/api/homeappliances/events"
event_clients: list[BaseHTTPRequestHandler] = []
event_clients_lock = Lock()
history_manager: HistoryManager | None = None
event_stream_thread: threading.Thread | None = None
event_stream_running = False  # Flag, ob Worker läuft
event_stream_stop_event = threading.Event()  # Event zum Stoppen des Workers
history_queue: Queue = Queue()
history_worker_thread: threading.Thread | None = None


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
            # Versuche zuerst direkt zu aktivieren - schneller als erst Status zu prüfen
            try:
                client.set_setting("BSH.Common.Setting.PowerState", "BSH.Common.EnumType.PowerState.On")
                self._send_json({"status": "activated", "message": "Gerät wurde aktiviert"}, status_code=200)
                return
            except RuntimeError:
                # Wenn Aktivierung fehlschlägt, prüfe ob Gerät bereits aktiv ist
                try:
                    status = client.get_status()
                    for item in status.get("data", {}).get("status", []):
                        if item.get("key") == "BSH.Common.Status.OperationState":
                            op_state = item.get("value")
                            if op_state != "BSH.Common.EnumType.OperationState.Inactive":
                                self._send_json({"status": "already_on", "message": "Gerät ist bereits aktiviert"}, status_code=200)
                                return
                            break
                    
                    # Fallback: Prüfe Settings
                    settings = client.get_settings()
                    for setting in settings.get("data", {}).get("settings", []):
                        if setting.get("key") == "BSH.Common.Setting.PowerState":
                            power_state = setting.get("value")
                            if power_state == "BSH.Common.EnumType.PowerState.On":
                                self._send_json({"status": "already_on", "message": "Gerät ist bereits aktiviert"}, status_code=200)
                                return
                            break
                    
                    self._send_json({"status": "unknown", "message": "Konnte PowerState nicht bestimmen"}, status_code=200)
                except Exception:
                    # Wenn Status-Prüfung fehlschlägt, nehme an dass Aktivierung erfolgreich war
                    self._send_json({"status": "activated", "message": "Gerät wurde aktiviert"}, status_code=200)
                    
        except requests.exceptions.Timeout:
            self._send_error(504, "API-Anfrage hat das Timeout überschritten")
        except Exception as e:
            self._send_error(500, f"Fehler beim Aktivieren: {str(e)}")

    def _handle_status(self, client: HomeConnectClient) -> None:
        """Gibt den Gerätestatus zurück."""
        status = client.get_status()
        self._send_json(status, status_code=200)

    def _handle_extended_status(self, client: HomeConnectClient) -> None:
        """Gibt erweiterten Status mit Settings und Programmen zurück."""
        try:
            status = client.get_status()
            settings = client.get_settings()
            
            # Versuche Programme abzurufen (können fehlschlagen wenn Gerät nicht bereit)
            programs_available = {}
            program_selected = {}
            program_active = {}
            
            try:
                programs_available = client.get_programs()
            except Exception:
                pass
            
            try:
                program_selected = client.get_selected_program()
            except Exception:
                pass
            
            try:
                program_active = client.get_active_program()
            except Exception:
                pass

            extended_status = {
                "status": status,
                "settings": settings,
                "programs": {
                    "available": programs_available,
                    "selected": program_selected,
                    "active": program_active,
                },
            }
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
                usage = history_manager.get_daily_usage(days)
                self._send_json({"daily_usage": usage}, status_code=200)
            elif query_params.get("program_counts"):
                # Programm-Zählungen
                counts = history_manager.get_program_counts()
                self._send_json({"program_counts": counts}, status_code=200)
            else:
                # Standard-History
                history = history_manager.get_history(event_type, limit_int, before_timestamp)
                self._send_json({"history": history}, status_code=200)
        except ValueError as e:
            self._send_error(400, f"Ungültiger Parameter: {str(e)}")
        except Exception as e:
            if CoffeeHandler.enable_logging:
                print(f"Fehler beim Laden der History: {e}")
            self._send_error(500, "Fehler beim Laden der History")

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
        # SSE-Header senden
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Client zur Liste hinzufügen
        with event_clients_lock:
            event_clients.append(self)

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
            # Client aus Liste entfernen
            with event_clients_lock:
                if self in event_clients:
                    event_clients.remove(self)

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
        from scripts.brew_espresso import ESPRESSO_KEY, build_options

        try:
            # Aktiviere Gerät falls nötig
            try:
                settings = client.get_settings()
                for setting in settings.get("data", {}).get("settings", []):
                    if setting.get("key") == "BSH.Common.Setting.PowerState":
                        if setting.get("value") == "BSH.Common.EnumType.PowerState.Standby":
                            client.set_setting("BSH.Common.Setting.PowerState", "BSH.Common.EnumType.PowerState.On")
            except Exception as e:
                if CoffeeHandler.enable_logging:
                    print(f"Fehler beim Aktivieren des Geräts: {e}")

            # Wähle Programm aus
            options = build_options(fill_ml, None)
            try:
                client.clear_selected_program()
            except Exception:
                pass

            client.select_program(ESPRESSO_KEY, options=options)
            client.start_program()

            self._send_json({"status": "started", "message": f"Espresso ({fill_ml} ml) wird zubereitet"}, status_code=200)
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


def history_worker() -> None:
    """Hintergrund-Thread, der Events aus der Queue speichert."""
    global history_manager
    
    while True:
        try:
            # Warte auf Event in der Queue (blockierend, aber in separatem Thread)
            event_type, data = history_queue.get(timeout=1)
            
            if history_manager:
                try:
                    history_manager.add_event(event_type, data)
                except Exception as e:
                    if CoffeeHandler.enable_logging:
                        print(f"Fehler beim Speichern von Event in History: {e}")
            
            history_queue.task_done()
        except Exception:
            # Timeout oder anderer Fehler - einfach weiter
            pass


def event_stream_worker() -> None:
    """Hintergrund-Thread, der den HomeConnect Events-Stream abhört.
    
    Läuft IMMER, um Events für die History zu sammeln.
    Sendet Events nur an verbundene Clients (spart Ressourcen).
    """
    global history_manager, event_stream_running

    while not event_stream_stop_event.is_set():
        try:
            # Timeout für Config und Client-Erstellung - in try-except, damit Fehler nicht den Server blockieren
            try:
                config = load_config()
                client = HomeConnectClient(config)
                token = client.get_access_token()
            except Exception as e:
                if CoffeeHandler.enable_logging:
                    print(f"Events-Stream Worker: Fehler beim Laden der Config: {e}")
                time.sleep(10)  # Warte vor erneutem Versuch
                continue
                
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "text/event-stream",
            }

            if CoffeeHandler.enable_logging:
                print("Events-Stream Worker: Verbinde mit HomeConnect Events...")

            # SSEClient benötigt eine requests.Response, nicht direkt eine URL
            # Timeout für Verbindung, aber None für Stream (läuft endlos)
            try:
                response = requests.get(
                    EVENTS_URL,
                    headers=headers,
                    stream=True,
                    timeout=(10, None)  # 10 Sekunden für Verbindung, None für Stream
                )
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                if CoffeeHandler.enable_logging:
                    print(f"Events-Stream Worker: Verbindungsfehler: {e}")
                time.sleep(10)  # Längere Pause bei Verbindungsfehlern
                continue

            if CoffeeHandler.enable_logging:
                print("Events-Stream Worker: Verbunden, warte auf Events...")

            client = SSEClient(response)
            for event in client.events():
                if not event.data:
                    continue

                try:
                    payload = json.loads(event.data)
                    event_type = event.event or "message"

                    # Alle Events für History speichern (asynchron über Queue)
                    if history_manager:
                        try:
                            # Füge Event zur Queue hinzu (nicht-blockierend)
                            history_queue.put_nowait((
                                event_type.lower(),
                                payload,
                            ))
                            
                            # Zusätzlich spezielle Events für Statistiken
                            if event_type == "STATUS":
                                history_queue.put_nowait((
                                    "status_changed",
                                    {
                                        "event": event_type,
                                        "payload": payload,
                                    },
                                ))
                            elif event_type in ("EVENT", "NOTIFY"):
                                # Programm-Events speichern
                                # Events haben Struktur: {"haId": "...", "items": [{"key": "...", "value": ...}]}
                                items = payload.get("items", [])
                                for item in items:
                                    item_key = item.get("key")
                                    item_value = item.get("value")
                                    
                                    # ActiveProgram Event: Wenn value nicht null ist, wurde ein Programm gestartet
                                    if item_key == "BSH.Common.Root.ActiveProgram" and item_value:
                                        # item_value ist ein Programm-Objekt mit "key" und "options"
                                        if isinstance(item_value, dict):
                                            history_queue.put_nowait((
                                                "program_started",
                                                {
                                                    "program": item_value.get("key", "Unknown"),
                                                    "options": item_value.get("options", []),
                                                },
                                            ))
                        except Exception as e:
                            # Fehler beim Hinzufügen zur Queue sollten den Stream nicht stoppen
                            if CoffeeHandler.enable_logging:
                                print(f"Fehler beim Hinzufügen von Event zur Queue: {e}")

                    # Event an alle verbundenen Clients senden (nur wenn welche verbunden sind)
                    with event_clients_lock:
                        if event_clients:  # Nur senden, wenn Clients verbunden sind
                            disconnected_clients = []
                            for client_handler in event_clients:
                                try:
                                    client_handler._send_sse_event(event_type, payload)
                                except (BrokenPipeError, ConnectionResetError, OSError):
                                    # Client hat Verbindung geschlossen - normal, nicht loggen
                                    disconnected_clients.append(client_handler)
                            
                            # Entferne getrennte Clients
                            for client in disconnected_clients:
                                if client in event_clients:
                                    event_clients.remove(client)

                except json.JSONDecodeError:
                    # Nicht-JSON Event ignorieren
                    pass
                except Exception as e:
                    if CoffeeHandler.enable_logging:
                        print(f"Fehler beim Verarbeiten von Event: {e}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            if CoffeeHandler.enable_logging:
                print(f"Fehler im Events-Stream: {e}")
            time.sleep(5)  # Warte vor Reconnect
    
    event_stream_running = False
    if CoffeeHandler.enable_logging:
        print("Events-Stream Worker beendet.")


def _start_event_stream_worker() -> None:
    """Startet den Event-Stream-Worker, wenn noch nicht gestartet."""
    global event_stream_thread, event_stream_running, event_stream_stop_event
    
    if event_stream_running:
        return
    
    event_stream_stop_event.clear()
    event_stream_running = True
    event_stream_thread = threading.Thread(target=event_stream_worker, daemon=True)
    event_stream_thread.start()
    if CoffeeHandler.enable_logging:
        print("Events-Stream Worker gestartet (Client verbunden)")


def _stop_event_stream_worker() -> None:
    """Stoppt den Event-Stream-Worker."""
    global event_stream_running, event_stream_stop_event
    
    if not event_stream_running:
        return
    
    event_stream_stop_event.set()
    if CoffeeHandler.enable_logging:
        print("Events-Stream Worker wird gestoppt (keine Clients mehr verbunden)")


def main() -> None:
    global history_manager, event_stream_thread, history_worker_thread

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

    # History-Worker Thread starten (für asynchrones Speichern)
    history_worker_thread = threading.Thread(target=history_worker, daemon=True)
    history_worker_thread.start()

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
    
    # Events-Stream Thread starten (NACH Server-Start, damit Server nicht blockiert)
    # Worker läuft IMMER, um Events für die History zu sammeln
    # Sendet Events nur an verbundene Clients (spart Ressourcen)
    def start_event_worker_delayed():
        time.sleep(2)  # Warte 2 Sekunden, damit Server vollständig gestartet ist
        global event_stream_thread
        if CoffeeHandler.enable_logging:
            print("Events-Stream Worker wird gestartet (für History-Persistierung)...")
        _start_event_stream_worker()
    
    worker_starter = threading.Thread(target=start_event_worker_delayed, daemon=True)
    worker_starter.start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer wird beendet...")
        server.shutdown()


if __name__ == "__main__":
    main()

