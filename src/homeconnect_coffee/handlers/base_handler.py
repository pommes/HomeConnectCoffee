"""Base handler for common functionality."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlencode, urlparse

from ..errors import ErrorCode, ErrorHandler

# Logger for handlers
logger = logging.getLogger(__name__)


class BaseHandler(BaseHTTPRequestHandler):
    """Base class for all HTTP handlers with common functionality.
    
    This class is used as a router and provides common functionality
    for all handler methods. Handler methods are static and take
    the router (BaseHandler instance) as a parameter.
    """

    enable_logging = True
    api_token: str | None = None
    error_handler: ErrorHandler | None = None

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
            logger.info(f"{client_ip} - {method} {path} - {code}")

    def _mask_token_in_path(self, path: str) -> str:
        """Masks token parameters in the path for logging.
        
        Args:
            path: The path with possible token parameter
            
        Returns:
            Path with masked token
        """
        if "token=" not in path:
            return path
        
        parsed = urlparse(path)
        query_params = parse_qs(parsed.query)
        
        if "token" in query_params:
            # Mask token
            query_params["token"] = ["__MASKED__"]
            new_query = urlencode(query_params, doseq=True)
            return f"{parsed.path}?{new_query}"
        
        return path

    def _check_auth(self) -> bool:
        """Checks authentication via header or query parameter.
        
        Returns:
            True if authenticated, False otherwise
        """
        if self.api_token is None:
            return True  # No token configured = open

        # Check Authorization header
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token == self.api_token:
                return True

        # Check query parameter
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        token_param = query_params.get("token", [None])[0]
        if token_param == self.api_token:
            return True

        return False

    def _require_auth(self) -> bool:
        """Checks authentication and sends 401 on error.
        
        Returns:
            True if authenticated, False if 401 was sent
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
        """Sends a JSON response.
        
        Args:
            data: The JSON data
            status_code: HTTP status code
        """
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        response_body = json.dumps(data, indent=2).encode("utf-8")
        self.wfile.write(response_body)
        # log_request is automatically called by BaseHTTPRequestHandler

    def _send_error(self, code: int, message: str) -> None:
        """Sends an error response (legacy method, for backward compatibility).
        
        Args:
            code: HTTP status code
            message: Error message
        """
        response = {"error": message, "code": code}
        self._send_error_response(code, response)

    def _send_error_response(self, code: int, response: dict) -> None:
        """Sends an error response in a consistent format.
        
        Args:
            code: HTTP status code
            response: Error response dict
        """
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        error_body = json.dumps(response, indent=2).encode("utf-8")
        self.wfile.write(error_body)
        # log_request is automatically called by BaseHTTPRequestHandler

    def _parse_path(self) -> tuple[str, dict]:
        """Parses the request path and query parameters.
        
        Returns:
            Tuple of (path, query parameters dict)
        """
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        return parsed_path.path, query_params

    def _send_not_found(self) -> None:
        """Sends 404 Not Found response."""
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
        """Suppresses standard logging messages (only log_request is used)."""
        pass

