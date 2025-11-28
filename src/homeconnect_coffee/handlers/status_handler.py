"""Handler für Status-Endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..client import HomeConnectClient
from ..config import load_config
from ..services import StatusService

if TYPE_CHECKING:
    from .base_handler import BaseHandler
    from ..middleware.auth_middleware import AuthMiddleware


class StatusHandler:
    """Handler für Status-Endpoints: /status und /api/status.
    
    Handler-Methoden sind statisch und nehmen den Router als Parameter.
    """

    @staticmethod
    def handle_status(router: "BaseHandler", auth_middleware: "AuthMiddleware | None" = None) -> None:
        """Gibt den Gerätestatus zurück.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
            auth_middleware: Optional AuthMiddleware für Authentifizierung.
                           Wenn None, wird router._require_auth() verwendet (Legacy).
        """
        # Verwende Middleware falls vorhanden, sonst Legacy-Methode
        if auth_middleware:
            if not auth_middleware.require_auth(router):
                return
        elif not router._require_auth():
            return

        try:
            config = load_config()
            client = HomeConnectClient(config)
            status_service = StatusService(client)
            status = status_service.get_status()
            router._send_json(status, status_code=200)
        except Exception as e:
            StatusHandler._handle_error(router, e, "Fehler beim Abrufen des Status")

    @staticmethod
    def handle_extended_status(router: "BaseHandler", auth_middleware: "AuthMiddleware | None" = None) -> None:
        """Gibt erweiterten Status mit Settings und Programmen zurück.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
            auth_middleware: Optional AuthMiddleware für Authentifizierung.
                           Wenn None, wird router._require_auth() verwendet (Legacy).
        """
        # Verwende Middleware falls vorhanden, sonst Legacy-Methode
        if auth_middleware:
            if not auth_middleware.require_auth(router):
                return
        elif not router._require_auth():
            return

        try:
            config = load_config()
            client = HomeConnectClient(config)
            status_service = StatusService(client)
            extended_status = status_service.get_extended_status()
            router._send_json(extended_status, status_code=200)
        except Exception as e:
            StatusHandler._handle_error(router, e, "Fehler beim Abrufen des Status")

    @staticmethod
    def _handle_error(router: "BaseHandler", exception: Exception, default_message: str) -> None:
        """Behandelt einen Fehler und sendet entsprechende Response.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
            exception: Die aufgetretene Exception
            default_message: Standard-Fehlermeldung
        """
        if router.error_handler:
            code, response = router.error_handler.handle_error(exception, default_message=default_message)
            router._send_error_response(code, response)
        else:
            router._send_error(500, f"{default_message}: {str(exception)}")

