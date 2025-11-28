"""Handler for status endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..client import HomeConnectClient
from ..config import load_config
from ..services import StatusService

if TYPE_CHECKING:
    from .base_handler import BaseHandler
    from ..middleware.auth_middleware import AuthMiddleware


class StatusHandler:
    """Handler for status endpoints: /status and /api/status.
    
    Handler methods are static and take the router as a parameter.
    """

    @staticmethod
    def handle_status(router: "BaseHandler", auth_middleware: "AuthMiddleware | None" = None) -> None:
        """Returns the device status.
        
        Args:
            router: The router (BaseHandler instance) with request context
            auth_middleware: Optional AuthMiddleware for authentication.
                           If None, router._require_auth() is used (legacy).
        """
        # Use middleware if present, otherwise legacy method
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
            StatusHandler._handle_error(router, e, "Error retrieving status")

    @staticmethod
    def handle_extended_status(router: "BaseHandler", auth_middleware: "AuthMiddleware | None" = None) -> None:
        """Returns extended status with settings and programs.
        
        Args:
            router: The router (BaseHandler instance) with request context
            auth_middleware: Optional AuthMiddleware for authentication.
                           If None, router._require_auth() is used (legacy).
        """
        # Use middleware if present, otherwise legacy method
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
            StatusHandler._handle_error(router, e, "Error retrieving status")

    @staticmethod
    def _handle_error(router: "BaseHandler", exception: Exception, default_message: str) -> None:
        """Handles an error and sends appropriate response.
        
        Args:
            router: The router (BaseHandler instance) with request context
            exception: The exception that occurred
            default_message: Default error message
        """
        if router.error_handler:
            code, response = router.error_handler.handle_error(exception, default_message=default_message)
            router._send_error_response(code, response)
        else:
            router._send_error(500, f"{default_message}: {str(exception)}")

