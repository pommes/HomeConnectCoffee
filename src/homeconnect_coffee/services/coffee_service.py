"""Service für Coffee-Operationen (Wake, Brew)."""

from __future__ import annotations

from typing import Any, Dict

import requests

from ..client import HomeConnectClient
from ..config import HomeConnectConfig

ESPRESSO_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.Espresso"
FILL_OPTION = "ConsumerProducts.CoffeeMaker.Option.FillQuantity"


def build_options(fill_ml: int | None) -> list[dict[str, object]]:
    """Baut Options-Liste für Espresso-Programm."""
    options: list[dict[str, object]] = []
    if fill_ml is not None:
        options.append({"key": FILL_OPTION, "value": fill_ml})
    return options


class CoffeeService:
    """Service für Coffee-Operationen."""

    def __init__(self, client: HomeConnectClient) -> None:
        """Initialisiert den CoffeeService mit einem HomeConnectClient."""
        self.client = client

    def wake_device(self) -> Dict[str, Any]:
        """Aktiviert das Gerät aus dem Standby.
        
        Returns:
            Dict mit Status und Message:
            - {"status": "activated", "message": "..."}
            - {"status": "already_on", "message": "..."}
            - {"status": "unknown", "message": "..."}
        """
        # Versuche zuerst direkt zu aktivieren - schneller als erst Status zu prüfen
        try:
            self.client.set_setting("BSH.Common.Setting.PowerState", "BSH.Common.EnumType.PowerState.On")
            return {"status": "activated", "message": "Gerät wurde aktiviert"}
        except RuntimeError:
            # Wenn Aktivierung fehlschlägt, prüfe ob Gerät bereits aktiv ist
            try:
                status = self.client.get_status()
                for item in status.get("data", {}).get("status", []):
                    if item.get("key") == "BSH.Common.Status.OperationState":
                        op_state = item.get("value")
                        if op_state != "BSH.Common.EnumType.OperationState.Inactive":
                            return {"status": "already_on", "message": "Gerät ist bereits aktiviert"}
                        break
                
                # Fallback: Prüfe Settings
                settings = self.client.get_settings()
                for setting in settings.get("data", {}).get("settings", []):
                    if setting.get("key") == "BSH.Common.Setting.PowerState":
                        power_state = setting.get("value")
                        if power_state == "BSH.Common.EnumType.PowerState.On":
                            return {"status": "already_on", "message": "Gerät ist bereits aktiviert"}
                        break
                
                return {"status": "unknown", "message": "Konnte PowerState nicht bestimmen"}
            except Exception:
                # Wenn Status-Prüfung fehlschlägt, nehme an dass Aktivierung erfolgreich war
                return {"status": "activated", "message": "Gerät wurde aktiviert"}

    def brew_espresso(self, fill_ml: int) -> Dict[str, Any]:
        """Startet einen Espresso.
        
        Args:
            fill_ml: Füllmenge in ml (35-50 ml)
        
        Returns:
            Dict mit Status und Message:
            - {"status": "started", "message": "Espresso (X ml) wird zubereitet"}
        
        Raises:
            RuntimeError: Wenn das Programm nicht gestartet werden kann
        """
        # Aktiviere Gerät falls nötig
        try:
            settings = self.client.get_settings()
            for setting in settings.get("data", {}).get("settings", []):
                if setting.get("key") == "BSH.Common.Setting.PowerState":
                    if setting.get("value") == "BSH.Common.EnumType.PowerState.Standby":
                        self.client.set_setting("BSH.Common.Setting.PowerState", "BSH.Common.EnumType.PowerState.On")
        except Exception:
            # Fehler beim Aktivieren ignorieren, versuche trotzdem zu brühen
            pass

        # Wähle Programm aus
        options = build_options(fill_ml)
        try:
            self.client.clear_selected_program()
        except Exception:
            # Ignoriere Fehler, falls kein Programm ausgewählt ist
            pass

        self.client.select_program(ESPRESSO_KEY, options=options)
        self.client.start_program()

        return {"status": "started", "message": f"Espresso ({fill_ml} ml) wird zubereitet"}

