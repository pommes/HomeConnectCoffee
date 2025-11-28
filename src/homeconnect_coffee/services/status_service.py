"""Service for status queries."""

from __future__ import annotations

from typing import Any, Dict

from ..client import HomeConnectClient


class StatusService:
    """Service for status queries."""

    def __init__(self, client: HomeConnectClient) -> None:
        """Initializes the StatusService with a HomeConnectClient."""
        self.client = client

    def get_status(self) -> Dict[str, Any]:
        """Returns the device status.
        
        Returns:
            Dict with status data from the HomeConnect API
        """
        return self.client.get_status()

    def get_extended_status(self) -> Dict[str, Any]:
        """Returns extended status with settings and programs.
        
        Returns:
            Dict with:
            - status: Device status
            - settings: Device settings
            - programs: {
                - available: Available programs
                - selected: Selected program
                - active: Active program
              }
        """
        status = self.client.get_status()
        settings = self.client.get_settings()
        
        # Try to retrieve programs (may fail if device is not ready)
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

