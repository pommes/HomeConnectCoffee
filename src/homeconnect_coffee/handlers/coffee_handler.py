"""Handler for coffee operations (Wake, Brew)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..client import HomeConnectClient
from ..config import load_config
from ..services import CoffeeService
from ..services.coffee_service import PROGRAM_KEYS

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
    def handle_brew(
        router: "BaseHandler",
        fill_ml: int | None = None,
        program: str | None = None,
        auth_middleware: "AuthMiddleware | None" = None,
    ) -> None:
        """Starts a coffee program.
        
        Args:
            router: The router (BaseHandler instance) with request context
            fill_ml: Optional fill amount in milliliters (only for espresso/coffee)
            program: Optional program name (default: "espresso")
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
            # Default to espresso if no program specified (backward compatibility)
            program_name = (program or "espresso").lower().strip()
            
            # Validate program name
            if program_name not in PROGRAM_KEYS:
                router._send_error(400, f"Invalid program: '{program}'. Available programs: {', '.join(sorted(PROGRAM_KEYS.keys()))}")
                return
            
            program_key = PROGRAM_KEYS[program_name]
            
            config = load_config()
            client = HomeConnectClient(config)
            coffee_service = CoffeeService(client)
            
            # Get display name for response
            display_name = program_name.title() if program_name else "Program"
            if program_name == "latte macchiato" or program_name == "lattemacchiato":
                display_name = "Latte Macchiato"
            elif program_name == "caffè latte" or program_name == "caffelatte":
                display_name = "Caffè Latte"
            elif program_name == "hot water" or program_name == "hotwater":
                display_name = "Hot Water"
            elif program_name == "hot milk" or program_name == "hotmilk":
                display_name = "Hot Milk"
            elif program_name == "milk foam" or program_name == "milkfoam":
                display_name = "Milk Foam"
            
            result = coffee_service.brew_program(program_key, fill_ml=fill_ml, program_name=display_name)
            router._send_json(result, status_code=200)
        except ValueError as e:
            router._send_error(400, str(e))
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

