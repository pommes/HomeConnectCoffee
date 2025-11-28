"""Service für History-Verwaltung."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..history import HistoryManager


class HistoryService:
    """Service für History-Verwaltung."""

    def __init__(self, history_manager: HistoryManager) -> None:
        """Initialisiert den HistoryService mit einem HistoryManager."""
        self.history_manager = history_manager

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: Optional[int] = None,
        before_timestamp: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Gibt die Event-History zurück.
        
        Args:
            event_type: Optionaler Filter für Event-Typ
            limit: Maximale Anzahl Events
            before_timestamp: ISO 8601 Timestamp für Cursor-basierte Pagination
        
        Returns:
            Liste von Events
        """
        return self.history_manager.get_history(event_type, limit, before_timestamp)

    def get_program_counts(self) -> Dict[str, int]:
        """Gibt die Anzahl der Nutzung pro Programm zurück.
        
        Returns:
            Dict mit Programm-Keys als Keys und Anzahl als Values
        """
        return self.history_manager.get_program_counts()

    def get_daily_usage(self, days: int = 7) -> Dict[str, int]:
        """Gibt die tägliche Nutzung der letzten N Tage zurück.
        
        Args:
            days: Anzahl der Tage (Standard: 7)
        
        Returns:
            Dict mit Datum (YYYY-MM-DD) als Keys und Anzahl als Values
        """
        return self.history_manager.get_daily_usage(days)

