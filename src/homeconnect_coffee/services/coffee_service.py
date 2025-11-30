"""Service for coffee operations (Wake, Brew)."""

from __future__ import annotations

from typing import Any, Dict

import requests

from ..client import HomeConnectClient
from ..config import HomeConnectConfig

ESPRESSO_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.Espresso"
COFFEE_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.Coffee"
CAPPUCCINO_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.Cappuccino"
LATTE_MACCHIATO_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.LatteMacchiato"
CAFFE_LATTE_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.CaffeLatte"
AMERICANO_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.Americano"
HOT_WATER_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.HotWater"
HOT_MILK_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.HotMilk"
MILK_FOAM_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.MilkFoam"
RISTRETTO_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.Ristretto"
LUNGO_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.Lungo"

FILL_OPTION = "ConsumerProducts.CoffeeMaker.Option.FillQuantity"

# Mapping from program name (lowercase) to program key
PROGRAM_KEYS = {
    "espresso": ESPRESSO_KEY,
    "coffee": COFFEE_KEY,
    "cappuccino": CAPPUCCINO_KEY,
    "latte macchiato": LATTE_MACCHIATO_KEY,
    "lattemacchiato": LATTE_MACCHIATO_KEY,
    "caffè latte": CAFFE_LATTE_KEY,
    "caffelatte": CAFFE_LATTE_KEY,
    "americano": AMERICANO_KEY,
    "hot water": HOT_WATER_KEY,
    "hotwater": HOT_WATER_KEY,
    "hot milk": HOT_MILK_KEY,
    "hotmilk": HOT_MILK_KEY,
    "milk foam": MILK_FOAM_KEY,
    "milkfoam": MILK_FOAM_KEY,
    "ristretto": RISTRETTO_KEY,
    "lungo": LUNGO_KEY,
}

# Programs that support fill_ml option
PROGRAMS_WITH_FILL_ML = {"espresso", "coffee"}


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

    def brew_program(
        self, program_key: str, fill_ml: int | None = None, program_name: str | None = None
    ) -> Dict[str, Any]:
        """Starts a coffee program.
        
        Args:
            program_key: The program key (e.g., ESPRESSO_KEY, COFFEE_KEY)
            fill_ml: Optional fill amount in ml (only for programs that support it)
            program_name: Optional program name for display in response message
        
        Returns:
            Dict with status and message:
            - {"status": "started", "message": "Program (X ml) is being prepared"}
        
        Raises:
            RuntimeError: If the program cannot be started
            ValueError: If fill_ml is provided for a program that doesn't support it
        """
        # Validate fill_ml for programs that don't support it
        program_name_lower = (program_name or "").lower()
        if fill_ml is not None and program_name_lower not in PROGRAMS_WITH_FILL_ML:
            raise ValueError(f"Program '{program_name or program_key}' does not support fill_ml option")
        
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
        options = build_options(fill_ml) if fill_ml is not None else []
        try:
            self.client.clear_selected_program()
        except Exception:
            # Ignore errors if no program is selected
            pass

        self.client.select_program(program_key, options=options)
        self.client.start_program()

        # Build response message
        if fill_ml is not None:
            message = f"{program_name or 'Program'} ({fill_ml} ml) is being prepared"
        else:
            message = f"{program_name or 'Program'} is being prepared"

        return {"status": "started", "message": message}

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
        return self.brew_program(ESPRESSO_KEY, fill_ml=fill_ml, program_name="Espresso")

