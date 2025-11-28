"""Handler for history endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..api_monitor import get_monitor
from ..errors import ErrorCode
from ..history import HistoryManager
from ..services import HistoryService

if TYPE_CHECKING:
    from .base_handler import BaseHandler

# Global variables (set in server.py)
history_manager: HistoryManager | None = None


class HistoryHandler:
    """Handler for history endpoints: /api/history and /api/stats.
    
    Handler methods are static and take the router as a parameter.
    """

    @staticmethod
    def handle_history(router: "BaseHandler", query_params: dict) -> None:
        """Returns the history data.
        
        Args:
            router: The router (BaseHandler instance) with request context
            query_params: Query parameters from the request
        """
        global history_manager
        
        if history_manager is None:
            if router.error_handler:
                response = router.error_handler.create_error_response(
                    ErrorCode.INTERNAL_SERVER_ERROR,
                    "History manager not initialized",
                    ErrorCode.INTERNAL_SERVER_ERROR,
                )
                router._send_error_response(ErrorCode.INTERNAL_SERVER_ERROR, response)
            else:
                router._send_error(500, "History manager not initialized")
            return

        try:
            history_service = HistoryService(history_manager)

            event_type = query_params.get("type", [None])[0]
            limit = query_params.get("limit", [None])[0]
            # Limit to maximum 1000 to avoid server overload
            limit_int = min(int(limit), 1000) if limit and limit.isdigit() else None

            # Cursor-based pagination: before_timestamp
            before_timestamp = query_params.get("before_timestamp", [None])[0]

            if query_params.get("daily_usage"):
                # Daily usage
                days = min(int(query_params.get("days", ["7"])[0]), 365)  # Max 1 year
                usage = history_service.get_daily_usage(days)
                router._send_json({"daily_usage": usage}, status_code=200)
            elif query_params.get("program_counts"):
                # Program counts
                counts = history_service.get_program_counts()
                router._send_json({"program_counts": counts}, status_code=200)
            else:
                # Standard history
                history = history_service.get_history(event_type, limit_int, before_timestamp)
                router._send_json({"history": history}, status_code=200)
        except ValueError as e:
            if router.error_handler:
                code, response = router.error_handler.handle_error(e, default_message="Invalid parameter")
                router._send_error_response(code, response)
            else:
                router._send_error(400, f"Invalid parameter: {str(e)}")
        except Exception as e:
            if router.error_handler:
                code, response = router.error_handler.handle_error(e, default_message="Error loading history")
                router._send_error_response(code, response)
            else:
                router._send_error(500, "Error loading history")

    @staticmethod
    def handle_api_stats(router: "BaseHandler") -> None:
        """Returns the API call statistics.
        
        Args:
            router: The router (BaseHandler instance) with request context
        """
        try:
            # api_stats.json is in project root (2 levels above handlers/)
            stats_path = Path(__file__).parent.parent.parent.parent / "api_stats.json"
            monitor = get_monitor(stats_path)
            stats = monitor.get_stats()
            router._send_json(stats, status_code=200)
        except Exception as e:
            if router.error_handler:
                code, response = router.error_handler.handle_error(e, default_message="Error loading API statistics")
                router._send_error_response(code, response)
            else:
                router._send_error(500, "Error loading API statistics")

