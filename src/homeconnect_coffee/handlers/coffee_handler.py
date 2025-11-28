"""Handler for coffee operations (Wake, Brew)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..client import HomeConnectClient
from ..config import load_config
from ..services import CoffeeService

if TYPE_CHECKING:
    from .base_handler import BaseHandler
    from ..middleware.auth_middleware import AuthMiddleware


class CoffeeHandler:
    """Handler for coffee operations: Wake and Brew.
    
    Handler methods are static and take the router as a parameter.
    """

    @staticmethod
    def handle_wake(router: "BaseHandler", auth_middleware: "AuthMiddleware | None" = None) -> None:
        """Activates the device from standby.
        
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
            coffee_service = CoffeeService(client)
            result = coffee_service.wake_device()
            router._send_json(result, status_code=200)
        except Exception as e:
            CoffeeHandler._handle_error(router, e, "Error activating device")

    @staticmethod
    def handle_brew(router: "BaseHandler", fill_ml: int, auth_middleware: "AuthMiddleware | None" = None) -> None:
        """Starts an espresso.
        
        Args:
            router: The router (BaseHandler instance) with request context
            fill_ml: Fill amount in milliliters
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
            coffee_service = CoffeeService(client)
            result = coffee_service.brew_espresso(fill_ml)
            router._send_json(result, status_code=200)
        except Exception as e:
            CoffeeHandler._handle_error(router, e, "Error starting program")

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

