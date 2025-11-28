"""Service für Status-Abfragen."""

from __future__ import annotations

from typing import Any, Dict

from ..client import HomeConnectClient


class StatusService:
    """Service für Status-Abfragen."""

    def __init__(self, client: HomeConnectClient) -> None:
        """Initialisiert den StatusService mit einem HomeConnectClient."""
        self.client = client

    def get_status(self) -> Dict[str, Any]:
        """Gibt den Gerätestatus zurück.
        
        Returns:
            Dict mit Status-Daten von der HomeConnect API
        """
        return self.client.get_status()

    def get_extended_status(self) -> Dict[str, Any]:
        """Gibt erweiterten Status mit Settings und Programmen zurück.
        
        Returns:
            Dict mit:
            - status: Gerätestatus
            - settings: Geräte-Einstellungen
            - programs: {
                - available: Verfügbare Programme
                - selected: Ausgewähltes Programm
                - active: Aktives Programm
              }
        """
        status = self.client.get_status()
        settings = self.client.get_settings()
        
        # Versuche Programme abzurufen (können fehlschlagen wenn Gerät nicht bereit)
        programs_available = {}
        program_selected = {}
        program_active = {}
        
        try:
            programs_available = self.client.get_programs()
        except Exception:
            pass
        
        try:
            program_selected = self.client.get_selected_program()
        except Exception:
            pass
        
        try:
            program_active = self.client.get_active_program()
        except Exception:
            pass

        return {
            "status": status,
            "settings": settings,
            "programs": {
                "available": programs_available,
                "selected": program_selected,
                "active": program_active,
            },
        }

