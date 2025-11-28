"""Service for history management."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..history import HistoryManager


class HistoryService:
    """Service for history management."""

    def __init__(self, history_manager: HistoryManager) -> None:
        """Initializes the HistoryService with a HistoryManager."""
        self.history_manager = history_manager

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: Optional[int] = None,
        before_timestamp: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns the event history.
        
        Args:
            event_type: Optional filter for event type
            limit: Maximum number of events
            before_timestamp: ISO 8601 timestamp for cursor-based pagination
        
        Returns:
            List of events
        """
        return self.history_manager.get_history(event_type, limit, before_timestamp)

    def get_program_counts(self) -> Dict[str, int]:
        """Returns the usage count per program.
        
        Returns:
            Dict with program keys as keys and count as values
        """
        return self.history_manager.get_program_counts()

    def get_daily_usage(self, days: int = 7) -> Dict[str, int]:
        """Returns the daily usage of the last N days.
        
        Args:
            days: Number of days (default: 7)
        
        Returns:
            Dict with date (YYYY-MM-DD) as keys and count as values
        """
        return self.history_manager.get_daily_usage(days)

