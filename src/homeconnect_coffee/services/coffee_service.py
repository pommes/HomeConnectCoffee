"""Service for coffee operations (Wake, Brew)."""

from __future__ import annotations

from typing import Any, Dict

import requests

from ..client import HomeConnectClient
from ..config import HomeConnectConfig

ESPRESSO_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.Espresso"
FILL_OPTION = "ConsumerProducts.CoffeeMaker.Option.FillQuantity"


def build_options(fill_ml: int | None) -> list[dict[str, object]]:
    """Builds options list for espresso program."""
    options: list[dict[str, object]] = []
    if fill_ml is not None:
        options.append({"key": FILL_OPTION, "value": fill_ml})
    return options


class CoffeeService:
    """Service for coffee operations."""

    def __init__(self, client: HomeConnectClient) -> None:
        """Initializes the CoffeeService with a HomeConnectClient."""
        self.client = client

    def wake_device(self) -> Dict[str, Any]:
        """Activates the device from standby.
        
        Returns:
            Dict with status and message:
            - {"status": "activated", "message": "..."}
            - {"status": "already_on", "message": "..."}
            - {"status": "unknown", "message": "..."}
        """
        # Try to activate directly first - faster than checking status first
        try:
            self.client.set_setting("BSH.Common.Setting.PowerState", "BSH.Common.EnumType.PowerState.On")
            return {"status": "activated", "message": "Device was activated"}
        except RuntimeError:
            # If activation fails, check if device is already active
            try:
                status = self.client.get_status()
                for item in status.get("data", {}).get("status", []):
                    if item.get("key") == "BSH.Common.Status.OperationState":
                        op_state = item.get("value")
                        if op_state != "BSH.Common.EnumType.OperationState.Inactive":
                            return {"status": "already_on", "message": "Device is already activated"}
                        break
                
                # Fallback: Check settings
                settings = self.client.get_settings()
                for setting in settings.get("data", {}).get("settings", []):
                    if setting.get("key") == "BSH.Common.Setting.PowerState":
                        power_state = setting.get("value")
                        if power_state == "BSH.Common.EnumType.PowerState.On":
                            return {"status": "already_on", "message": "Device is already activated"}
                        break
                
                return {"status": "unknown", "message": "Could not determine PowerState"}
            except Exception:
                # If status check fails, assume activation was successful
                return {"status": "activated", "message": "Device was activated"}

    def brew_espresso(self, fill_ml: int) -> Dict[str, Any]:
        """Starts an espresso.
        
        Args:
            fill_ml: Fill amount in ml (35-50 ml)
        
        Returns:
            Dict with status and message:
            - {"status": "started", "message": "Espresso (X ml) is being prepared"}
        
        Raises:
            RuntimeError: If the program cannot be started
        """
        # Activate device if necessary
        try:
            settings = self.client.get_settings()
            for setting in settings.get("data", {}).get("settings", []):
                if setting.get("key") == "BSH.Common.Setting.PowerState":
                    if setting.get("value") == "BSH.Common.EnumType.PowerState.Standby":
                        self.client.set_setting("BSH.Common.Setting.PowerState", "BSH.Common.EnumType.PowerState.On")
        except Exception:
            # Ignore activation errors, try to brew anyway
            pass

        # Select program
        options = build_options(fill_ml)
        try:
            self.client.clear_selected_program()
        except Exception:
            # Ignore errors if no program is selected
            pass

        self.client.select_program(ESPRESSO_KEY, options=options)
        self.client.start_program()

        return {"status": "started", "message": f"Espresso ({fill_ml} ml) is being prepared"}

