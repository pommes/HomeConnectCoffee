"""Router for request routing to specialized handlers."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from .base_handler import BaseHandler
from .coffee_handler import CoffeeHandler
from .dashboard_handler import DashboardHandler
from .history_handler import HistoryHandler
from .status_handler import StatusHandler


class RequestRouter(BaseHandler):
    """Router that forwards requests to specialized handlers."""

    enable_logging = True
    api_token: str | None = None
    error_handler = None

    def handle_one_request(self):
        """Overrides handle_one_request to catch BrokenPipeError."""
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client closed connection - normal, don't log
            pass

    def log_request(self, code="-", size="-"):
        """Logs requests when logging is enabled."""
        if self.enable_logging:
            client_ip = self.client_address[0]
            method = self.command
            path = self._mask_token_in_path(self.path)
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"{client_ip} - {method} {path} - {code}")
    
    def _mask_token_in_path(self, path: str) -> str:
        """Masks token parameters in the path for logging."""
        if "token=" not in path:
            return path
        
        parsed = urlparse(path)
        query_params = parse_qs(parsed.query)
        
        if "token" in query_params:
            # Mask token
            query_params["token"] = ["__MASKED__"]
            from urllib.parse import urlencode
            new_query = urlencode(query_params, doseq=True)
            return f"{parsed.path}?{new_query}"
        
        return path

    def log_message(self, format, *args):
        """Suppresses standard logging messages."""
        pass

    def do_GET(self):
        """Forwards GET requests to specialized handlers."""
        self._route_request()

    def do_POST(self):
        """Forwards POST requests to specialized handlers."""
        self._route_request()

    def _route_request(self) -> None:
        """Forwards requests to the appropriate handler.
        
        Routing logic:
        - /wake, /brew -> CoffeeHandler
        - /status, /api/status -> StatusHandler
        - /api/history, /api/stats -> HistoryHandler
        - /dashboard, /cert, /health, /events -> DashboardHandler
        
        Handler methods are static and take the router (self) as a parameter.
        """
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        # Public endpoints (no authentication)
        if path == "/dashboard":
            DashboardHandler.handle_dashboard(self)
            return
        elif path == "/cert":
            DashboardHandler.handle_cert_download(self)
            return
        elif path == "/health":
            DashboardHandler.handle_health(self)
            return
        elif path == "/events":
            DashboardHandler.handle_events_stream(self)
            return

        # History endpoints (public, read-only)
        if path == "/api/history":
            HistoryHandler.handle_history(self, query_params)
            return
        elif path == "/api/stats":
            HistoryHandler.handle_api_stats(self)
            return

        # Coffee endpoints (require authentication)
        if path == "/wake":
            CoffeeHandler.handle_wake(self, self.auth_middleware)
            return
        elif path == "/brew":
            if self.command == "GET":
                # Brew as GET with query parameter fill_ml
                fill_ml_param = query_params.get("fill_ml", [None])[0]
                fill_ml = int(fill_ml_param) if fill_ml_param and fill_ml_param.isdigit() else 50
                CoffeeHandler.handle_brew(self, fill_ml, self.auth_middleware)
            elif self.command == "POST":
                # Brew as POST with JSON body
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                data = json.loads(body) if body else {}
                fill_ml = data.get("fill_ml", 50)
                CoffeeHandler.handle_brew(self, fill_ml, self.auth_middleware)
            return

        # Status endpoints (require authentication)
        if path == "/status":
            StatusHandler.handle_status(self, self.auth_middleware)
            return
        elif path == "/api/status":
            StatusHandler.handle_extended_status(self, self.auth_middleware)
            return

        # 404 Not Found
        self._send_not_found()

