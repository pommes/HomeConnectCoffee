"""Handler für History-Endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..api_monitor import get_monitor
from ..errors import ErrorCode
from ..history import HistoryManager
from ..services import HistoryService

if TYPE_CHECKING:
    from .base_handler import BaseHandler

# Globale Variablen (werden in server.py gesetzt)
history_manager: HistoryManager | None = None


class HistoryHandler:
    """Handler für History-Endpoints: /api/history und /api/stats.
    
    Handler-Methoden sind statisch und nehmen den Router als Parameter.
    """

    @staticmethod
    def handle_history(router: "BaseHandler", query_params: dict) -> None:
        """Gibt die Verlaufsdaten zurück.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
            query_params: Query-Parameter aus dem Request
        """
        global history_manager
        
        if history_manager is None:
            if router.error_handler:
                response = router.error_handler.create_error_response(
                    ErrorCode.INTERNAL_SERVER_ERROR,
                    "History-Manager nicht initialisiert",
                    ErrorCode.INTERNAL_SERVER_ERROR,
                )
                router._send_error_response(ErrorCode.INTERNAL_SERVER_ERROR, response)
            else:
                router._send_error(500, "History-Manager nicht initialisiert")
            return

        try:
            history_service = HistoryService(history_manager)

            event_type = query_params.get("type", [None])[0]
            limit = query_params.get("limit", [None])[0]
            # Begrenze Limit auf maximal 1000, um Server-Überlastung zu vermeiden
            limit_int = min(int(limit), 1000) if limit and limit.isdigit() else None

            # Cursor-basierte Pagination: before_timestamp
            before_timestamp = query_params.get("before_timestamp", [None])[0]

            if query_params.get("daily_usage"):
                # Tägliche Nutzung
                days = min(int(query_params.get("days", ["7"])[0]), 365)  # Max 1 Jahr
                usage = history_service.get_daily_usage(days)
                router._send_json({"daily_usage": usage}, status_code=200)
            elif query_params.get("program_counts"):
                # Programm-Zählungen
                counts = history_service.get_program_counts()
                router._send_json({"program_counts": counts}, status_code=200)
            else:
                # Standard-History
                history = history_service.get_history(event_type, limit_int, before_timestamp)
                router._send_json({"history": history}, status_code=200)
        except ValueError as e:
            if router.error_handler:
                code, response = router.error_handler.handle_error(e, default_message="Ungültiger Parameter")
                router._send_error_response(code, response)
            else:
                router._send_error(400, f"Ungültiger Parameter: {str(e)}")
        except Exception as e:
            if router.error_handler:
                code, response = router.error_handler.handle_error(e, default_message="Fehler beim Laden der History")
                router._send_error_response(code, response)
            else:
                router._send_error(500, "Fehler beim Laden der History")

    @staticmethod
    def handle_api_stats(router: "BaseHandler") -> None:
        """Gibt die API-Call-Statistiken zurück.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
        """
        try:
            # api_stats.json liegt im Projekt-Root (2 Ebenen über handlers/)
            stats_path = Path(__file__).parent.parent.parent.parent / "api_stats.json"
            monitor = get_monitor(stats_path)
            stats = monitor.get_stats()
            router._send_json(stats, status_code=200)
        except Exception as e:
            if router.error_handler:
                code, response = router.error_handler.handle_error(e, default_message="Fehler beim Laden der API-Statistiken")
                router._send_error_response(code, response)
            else:
                router._send_error(500, "Fehler beim Laden der API-Statistiken")

