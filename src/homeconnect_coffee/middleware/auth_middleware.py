"""Authentifizierungs-Middleware für HTTP-Handler."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from ..errors import ErrorCode

if TYPE_CHECKING:
    from ..handlers.base_handler import BaseHandler


class AuthMiddleware:
    """Middleware für Token-basierte Authentifizierung.
    
    Unterstützt:
    - Bearer Token im Authorization Header
    - Token als Query-Parameter (?token=...)
    
    Die Middleware kann als Wrapper für Handler-Methoden verwendet werden
    oder direkt in Handler-Methoden aufgerufen werden.
    """

    def __init__(self, api_token: str | None = None, error_handler=None):
        """Initialisiert die Auth-Middleware.
        
        Args:
            api_token: Das zu prüfende API-Token. Wenn None, ist Authentifizierung deaktiviert.
            error_handler: Optionaler ErrorHandler für Fehler-Responses.
        """
        self.api_token = api_token
        self.error_handler = error_handler

    def check_auth(self, router: "BaseHandler") -> bool:
        """Prüft die Authentifizierung via Header oder Query-Parameter.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
            
        Returns:
            True wenn authentifiziert, False sonst
        """
        if self.api_token is None:
            return True  # Kein Token konfiguriert = offen

        # Prüfe Authorization Header
        auth_header = router.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token == self.api_token:
                return True

        # Prüfe Query-Parameter
        parsed_path = urlparse(router.path)
        query_params = parse_qs(parsed_path.query)
        token_param = query_params.get("token", [None])[0]
        if token_param == self.api_token:
            return True

        return False

    def require_auth(self, router: "BaseHandler") -> bool:
        """Prüft Authentifizierung und sendet 401 bei Fehler.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
            
        Returns:
            True wenn authentifiziert, False wenn 401 gesendet wurde
        """
        if not self.check_auth(router):
            if self.error_handler:
                response = self.error_handler.create_error_response(
                    ErrorCode.UNAUTHORIZED,
                    "Unauthorized - Invalid or missing API token",
                    ErrorCode.UNAUTHORIZED,
                )
                router._send_error_response(ErrorCode.UNAUTHORIZED, response)
            else:
                router._send_error(401, "Unauthorized - Invalid or missing API token")
            return False
        return True

    def __call__(self, router: "BaseHandler") -> bool:
        """Ermöglicht Middleware als Callable zu verwenden.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
            
        Returns:
            True wenn authentifiziert, False wenn 401 gesendet wurde
        """
        return self.require_auth(router)

