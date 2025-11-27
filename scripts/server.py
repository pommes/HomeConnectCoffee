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
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode

from homeconnect_coffee.client import HomeConnectClient
from homeconnect_coffee.config import load_config


class CoffeeHandler(BaseHTTPRequestHandler):
    enable_logging = True
    api_token: str | None = None

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
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Öffentliche Endpoints (keine Authentifizierung)
        if path == "/cert":
            self._handle_cert_download()
            return
        elif path == "/health":
            self._send_json({"status": "ok"}, status_code=200)
            return

        # Prüfe Authentifizierung für alle anderen Endpoints
        if not self._check_auth():
            self._send_error(401, "Unauthorized - Invalid or missing API token")
            return

        try:
            config = load_config()
            client = HomeConnectClient(config)

            if path == "/wake":
                self._handle_wake(client)
            elif path == "/status":
                self._handle_status(client)
            else:
                self._send_error(404, "Not Found")

        except Exception as e:
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

    server = HTTPServer((args.host, args.port), CoffeeHandler)

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
    print(f"   - GET  /cert   - Download SSL-Zertifikat (öffentlich)")
    print(f"   - GET  /wake   - Aktiviert das Gerät")
    print(f"   - GET  /status - Zeigt den Status")
    print(f"   - POST /brew   - Startet einen Espresso (JSON: {{\"fill_ml\": 50}})")
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
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer wird beendet...")
        server.shutdown()


if __name__ == "__main__":
    main()

