"""Base-Handler für gemeinsame Funktionalität."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlencode, urlparse

from ..errors import ErrorCode, ErrorHandler

# Logger für Handler
logger = logging.getLogger(__name__)


class BaseHandler(BaseHTTPRequestHandler):
    """Basis-Klasse für alle HTTP-Handler mit gemeinsamer Funktionalität.
    
    Diese Klasse wird als Router verwendet und stellt gemeinsame Funktionalität
    für alle Handler-Methoden bereit. Handler-Methoden sind statisch und nehmen
    den Router (BaseHandler-Instanz) als Parameter.
    """

    enable_logging = True
    api_token: str | None = None
    error_handler: ErrorHandler | None = None

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
            client_ip = self.client_address[0]
            method = self.command
            path = self._mask_token_in_path(self.path)
            logger.info(f"{client_ip} - {method} {path} - {code}")

    def _mask_token_in_path(self, path: str) -> str:
        """Maskiert Token-Parameter im Pfad für das Logging.
        
        Args:
            path: Der Pfad mit möglichem Token-Parameter
            
        Returns:
            Pfad mit maskiertem Token
        """
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
        """Prüft die Authentifizierung via Header oder Query-Parameter.
        
        Returns:
            True wenn authentifiziert, False sonst
        """
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

    def _require_auth(self) -> bool:
        """Prüft Authentifizierung und sendet 401 bei Fehler.
        
        Returns:
            True wenn authentifiziert, False wenn 401 gesendet wurde
        """
        if not self._check_auth():
            if self.error_handler:
                response = self.error_handler.create_error_response(
                    ErrorCode.UNAUTHORIZED,
                    "Unauthorized - Invalid or missing API token",
                    ErrorCode.UNAUTHORIZED,
                )
                self._send_error_response(ErrorCode.UNAUTHORIZED, response)
            else:
                self._send_error(401, "Unauthorized - Invalid or missing API token")
            return False
        return True

    def _send_json(self, data: dict, status_code: int = 200) -> None:
        """Sendet eine JSON-Response.
        
        Args:
            data: Die JSON-Daten
            status_code: HTTP-Status-Code
        """
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        response_body = json.dumps(data, indent=2).encode("utf-8")
        self.wfile.write(response_body)
        # log_request wird automatisch von BaseHTTPRequestHandler aufgerufen

    def _send_error(self, code: int, message: str) -> None:
        """Sendet eine Fehler-Response (Legacy-Methode, für Rückwärtskompatibilität).
        
        Args:
            code: HTTP-Status-Code
            message: Fehlermeldung
        """
        response = {"error": message, "code": code}
        self._send_error_response(code, response)

    def _send_error_response(self, code: int, response: dict) -> None:
        """Sendet eine Fehler-Response im konsistenten Format.
        
        Args:
            code: HTTP-Status-Code
            response: Error-Response-Dict
        """
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        error_body = json.dumps(response, indent=2).encode("utf-8")
        self.wfile.write(error_body)
        # log_request wird automatisch von BaseHTTPRequestHandler aufgerufen

    def _parse_path(self) -> tuple[str, dict]:
        """Parst den Request-Pfad und Query-Parameter.
        
        Returns:
            Tuple von (Pfad, Query-Parameter-Dict)
        """
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        return parsed_path.path, query_params

    def _send_not_found(self) -> None:
        """Sendet 404 Not Found Response."""
        if self.error_handler:
            response = self.error_handler.create_error_response(
                ErrorCode.NOT_FOUND,
                "Not Found",
                ErrorCode.NOT_FOUND,
            )
            self._send_error_response(ErrorCode.NOT_FOUND, response)
        else:
            self._send_error(404, "Not Found")

    def log_message(self, format, *args):
        """Unterdrückt Standard-Logging-Nachrichten (nur log_request wird verwendet)."""
        pass

