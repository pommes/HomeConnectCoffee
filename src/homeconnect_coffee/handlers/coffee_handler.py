"""Handler für Coffee-Operationen (Wake, Brew)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..client import HomeConnectClient
from ..config import load_config
from ..services import CoffeeService

if TYPE_CHECKING:
    from .base_handler import BaseHandler


class CoffeeHandler:
    """Handler für Coffee-Operationen: Wake und Brew.
    
    Handler-Methoden sind statisch und nehmen den Router als Parameter.
    """

    @staticmethod
    def handle_wake(router: "BaseHandler") -> None:
        """Aktiviert das Gerät aus dem Standby.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
        """
        if not router._require_auth():
            return

        try:
            config = load_config()
            client = HomeConnectClient(config)
            coffee_service = CoffeeService(client)
            result = coffee_service.wake_device()
            router._send_json(result, status_code=200)
        except Exception as e:
            CoffeeHandler._handle_error(router, e, "Fehler beim Aktivieren")

    @staticmethod
    def handle_brew(router: "BaseHandler", fill_ml: int) -> None:
        """Startet einen Espresso.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
            fill_ml: Füllmenge in Millilitern
        """
        if not router._require_auth():
            return

        try:
            config = load_config()
            client = HomeConnectClient(config)
            coffee_service = CoffeeService(client)
            result = coffee_service.brew_espresso(fill_ml)
            router._send_json(result, status_code=200)
        except Exception as e:
            CoffeeHandler._handle_error(router, e, "Fehler beim Starten des Programms")

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

