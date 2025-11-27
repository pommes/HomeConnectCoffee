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
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from homeconnect_coffee.client import HomeConnectClient
from homeconnect_coffee.config import load_config


class CoffeeHandler(BaseHTTPRequestHandler):
    enable_logging = True

    def log_request(self, code="-", size="-"):
        """Loggt Requests wenn Logging aktiviert ist."""
        if self.enable_logging:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            client_ip = self.client_address[0]
            method = self.command
            path = self.path
            print(f"[{timestamp}] {client_ip} - {method} {path} - {code}")

    def log_message(self, format, *args):
        """Unterdrückt Standard-Logging-Nachrichten (nur log_request wird verwendet)."""
        # Wir verwenden nur log_request für Request-Logging
        pass
    def do_GET(self):
        """Behandelt GET-Requests für Wake und Status."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        try:
            config = load_config()
            client = HomeConnectClient(config)

            if path == "/wake":
                self._handle_wake(client)
            elif path == "/status":
                self._handle_status(client)
            elif path == "/health":
                self._send_json({"status": "ok"}, status_code=200)
            else:
                self._send_error(404, "Not Found")

        except Exception as e:
            self._send_error(500, str(e))

    def do_POST(self):
        """Behandelt POST-Requests für Brew."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        try:
            config = load_config()
            client = HomeConnectClient(config)

            if path == "/brew":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                data = json.loads(body) if body else {}
                fill_ml = data.get("fill_ml", 50)
                self._handle_brew(client, fill_ml)
            else:
                self._send_error(404, "Not Found")

        except Exception as e:
            self._send_error(500, str(e))

    def _handle_wake(self, client: HomeConnectClient) -> None:
        """Aktiviert das Gerät aus dem Standby."""
        settings = client.get_settings()
        power_state = None
        for setting in settings.get("data", {}).get("settings", []):
            if setting.get("key") == "BSH.Common.Setting.PowerState":
                power_state = setting.get("value")
                break

        if power_state == "BSH.Common.EnumType.PowerState.Standby":
            client.set_setting("BSH.Common.Setting.PowerState", "BSH.Common.EnumType.PowerState.On")
            self._send_json({"status": "activated", "message": "Gerät wurde aktiviert"}, status_code=200)
        elif power_state == "BSH.Common.EnumType.PowerState.On":
            self._send_json({"status": "already_on", "message": "Gerät ist bereits aktiviert"}, status_code=200)
        else:
            self._send_json({"status": "unknown", "message": f"Unbekannter PowerState: {power_state}"}, status_code=200)

    def _handle_status(self, client: HomeConnectClient) -> None:
        """Gibt den Gerätestatus zurück."""
        status = client.get_status()
        self._send_json(status, status_code=200)

    def _handle_brew(self, client: HomeConnectClient, fill_ml: int) -> None:
        """Startet einen Espresso."""
        from scripts.brew_espresso import ESPRESSO_KEY, build_options

        # Aktiviere Gerät falls nötig
        try:
            settings = client.get_settings()
            for setting in settings.get("data", {}).get("settings", []):
                if setting.get("key") == "BSH.Common.Setting.PowerState":
                    if setting.get("value") == "BSH.Common.EnumType.PowerState.Standby":
                        client.set_setting("BSH.Common.Setting.PowerState", "BSH.Common.EnumType.PowerState.On")
        except Exception:
            pass

        # Wähle Programm aus
        options = build_options(fill_ml, None)
        try:
            client.clear_selected_program()
        except Exception:
            pass

        client.select_program(ESPRESSO_KEY, options=options)
        client.start_program()

        self._send_json({"status": "started", "message": f"Espresso ({fill_ml} ml) wird zubereitet"}, status_code=200)

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
    parser = argparse.ArgumentParser(description="HTTP-Server für Siri Shortcuts Integration")
    parser.add_argument("--port", type=int, default=8080, help="Port für den HTTP-Server (Standard: 8080)")
    parser.add_argument("--host", type=str, default="localhost", help="Host (Standard: localhost)")
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Deaktiviert das Request-Logging",
    )
    args = parser.parse_args()

    CoffeeHandler.enable_logging = not args.no_log

    server = HTTPServer((args.host, args.port), CoffeeHandler)
    print(f"☕ HomeConnect Coffee Server läuft auf http://{args.host}:{args.port}")
    print(f"   Endpoints:")
    print(f"   - GET  /wake   - Aktiviert das Gerät")
    print(f"   - GET  /status - Zeigt den Status")
    print(f"   - POST /brew   - Startet einen Espresso (JSON: {{\"fill_ml\": 50}})")
    if CoffeeHandler.enable_logging:
        print(f"   - Logging: aktiviert")
    else:
        print(f"   - Logging: deaktiviert")
    print(f"\n   Drücke Ctrl+C zum Beenden")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer wird beendet...")
        server.shutdown()


if __name__ == "__main__":
    main()

