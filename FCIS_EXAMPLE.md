# FCIS-Umstrukturierung: Praktisches Beispiel

Dieses Dokument zeigt eine konkrete FCIS-Umstrukturierung mit Functional Core und Imperative Shell, die **API Calls**, **DB-Zugriffe** und **weiteres I/O** kombiniert.

## Beispiel: CoffeeService → Functional Core + Shell

### Ziel
- **Core-Tests**: Keine Mocks benötigt (schnelle Tests)
- **Shell-Tests**: Mocks für I/O, aber weniger wegen Kombinatorik im Core

---

## 1. Functional Core (Reine Funktionen)

```python
# src/homeconnect_coffee/core/coffee_core.py
"""Functional Core für Coffee-Operationen - Reine Funktionen ohne I/O."""

from __future__ import annotations

from typing import Any, Dict

# Konstanten (aus coffee_service.py)
ESPRESSO_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.Espresso"
COFFEE_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.Coffee"
# ... weitere Programm-Keys

PROGRAMS_WITH_FILL_ML = {"espresso", "coffee"}


def build_options(fill_ml: int | None) -> list[dict[str, object]]:
    """Baut Options-Liste für Programm - Reine Funktion."""
    options: list[dict[str, object]] = []
    if fill_ml is not None:
        options.append({
            "key": "ConsumerProducts.CoffeeMaker.Option.FillQuantity",
            "value": fill_ml
        })
    return options


def validate_brew_request(
    program_key: str,
    program_name: str | None,
    fill_ml: int | None
) -> None:
    """Validiert Brew-Request - Reine Funktion, wirft ValueError bei Fehler.
    
    Args:
        program_key: Programm-Key
        program_name: Programm-Name (für Fehlermeldung)
        fill_ml: Optionale Füllmenge
        
    Raises:
        ValueError: Wenn fill_ml für Programm nicht unterstützt wird
    """
    if fill_ml is not None:
        program_name_lower = (program_name or "").lower()
        if program_name_lower not in PROGRAMS_WITH_FILL_ML:
            raise ValueError(
                f"Program '{program_name or program_key}' does not support fill_ml option"
            )


def build_brew_response(
    program_name: str | None,
    fill_ml: int | None
) -> Dict[str, Any]:
    """Baut Response-Message für Brew-Operation - Reine Funktion.
    
    Args:
        program_name: Programm-Name für Message
        fill_ml: Optionale Füllmenge
        
    Returns:
        Dict mit status und message
    """
    if fill_ml is not None:
        message = f"{program_name or 'Program'} ({fill_ml} ml) is being prepared"
    else:
        message = f"{program_name or 'Program'} is being prepared"
    
    return {"status": "started", "message": message}


def determine_wake_status(
    activation_successful: bool,
    operation_state: str | None,
    power_state: str | None
) -> Dict[str, Any]:
    """Bestimmt Wake-Status basierend auf Device-Daten - Reine Funktion.
    
    Args:
        activation_successful: Ob Activation erfolgreich war
        operation_state: OperationState vom Device (z.B. "BSH.Common.EnumType.OperationState.Run")
        power_state: PowerState vom Device (z.B. "BSH.Common.EnumType.PowerState.On")
        
    Returns:
        Dict mit status und message:
        - {"status": "activated", "message": "..."}
        - {"status": "already_on", "message": "..."}
        - {"status": "unknown", "message": "..."}
    """
    if activation_successful:
        return {"status": "activated", "message": "Device was activated"}
    
    # Prüfe OperationState
    if operation_state and operation_state != "BSH.Common.EnumType.OperationState.Inactive":
        return {"status": "already_on", "message": "Device is already activated"}
    
    # Prüfe PowerState
    if power_state == "BSH.Common.EnumType.PowerState.On":
        return {"status": "already_on", "message": "Device is already activated"}
    
    return {"status": "unknown", "message": "Could not determine PowerState"}


def extract_operation_state(status_data: Dict[str, Any]) -> str | None:
    """Extrahiert OperationState aus Status-Daten - Reine Funktion.
    
    Args:
        status_data: Status-Daten vom API (z.B. {"data": {"status": [...]}})
        
    Returns:
        OperationState-Wert oder None
    """
    status_items = status_data.get("data", {}).get("status", [])
    for item in status_items:
        if item.get("key") == "BSH.Common.Status.OperationState":
            return item.get("value")
    return None


def extract_power_state(settings_data: Dict[str, Any]) -> str | None:
    """Extrahiert PowerState aus Settings-Daten - Reine Funktion.
    
    Args:
        settings_data: Settings-Daten vom API (z.B. {"data": {"settings": [...]}})
        
    Returns:
        PowerState-Wert oder None
    """
    settings_items = settings_data.get("data", {}).get("settings", [])
    for setting in settings_items:
        if setting.get("key") == "BSH.Common.Setting.PowerState":
            return setting.get("value")
    return None


def should_activate_device(power_state: str | None) -> bool:
    """Bestimmt ob Device aktiviert werden sollte - Reine Funktion.
    
    Args:
        power_state: PowerState-Wert
        
    Returns:
        True wenn Device aktiviert werden sollte
    """
    return power_state == "BSH.Common.EnumType.PowerState.Standby"
```

---

## 2. Imperative Shell (I/O-Koordination)

```python
# src/homeconnect_coffee/shell/coffee_shell.py
"""Imperative Shell für Coffee-Operationen - Koordiniert I/O."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..client import HomeConnectClient
from ..core.coffee_core import (
    build_brew_response,
    build_options,
    determine_wake_status,
    extract_operation_state,
    extract_power_state,
    should_activate_device,
    validate_brew_request,
)
from ..history import HistoryManager

logger = logging.getLogger(__name__)


class CoffeeShell:
    """Shell für Coffee-Operationen - Koordiniert API Calls, DB-Zugriffe und weiteres I/O."""

    def __init__(
        self,
        client: HomeConnectClient,
        history_manager: HistoryManager | None = None,
    ) -> None:
        """Initialisiert CoffeeShell mit I/O-Dependencies.
        
        Args:
            client: HomeConnectClient für API Calls
            history_manager: Optional HistoryManager für Event-Persistierung
        """
        self.client = client
        self.history_manager = history_manager

    def wake_device(self) -> Dict[str, Any]:
        """Aktiviert Device von Standby - Shell koordiniert I/O.
        
        Returns:
            Dict mit status und message
        """
        # I/O: API Call - Versuche direkt zu aktivieren
        activation_successful = False
        try:
            self.client.set_setting(
                "BSH.Common.Setting.PowerState",
                "BSH.Common.EnumType.PowerState.On"
            )
            activation_successful = True
        except RuntimeError:
            # Activation fehlgeschlagen - prüfe Status
            pass

        # I/O: API Calls - Hole Device-Daten für Status-Prüfung
        operation_state = None
        power_state = None
        
        try:
            # I/O: API Call - Hole Status
            status_data = self.client.get_status()
            operation_state = extract_operation_state(status_data)
            
            # I/O: API Call - Hole Settings
            settings_data = self.client.get_settings()
            power_state = extract_power_state(settings_data)
        except Exception as e:
            # I/O-Fehler: Logging
            logger.warning(f"Error checking device status: {e}")
            # Wenn Status-Check fehlschlägt, nehmen wir an dass Activation erfolgreich war
            if activation_successful:
                return {"status": "activated", "message": "Device was activated"}

        # Functional Core: Reine Funktion - Bestimme Status
        result = determine_wake_status(activation_successful, operation_state, power_state)
        
        # I/O: Optional - Speichere Event in History
        if self.history_manager:
            try:
                self.history_manager.add_event("device_wake", {
                    "status": result["status"],
                    "operation_state": operation_state,
                    "power_state": power_state,
                })
            except Exception as e:
                logger.warning(f"Error saving wake event to history: {e}")

        return result

    def brew_program(
        self,
        program_key: str,
        fill_ml: int | None = None,
        program_name: str | None = None,
    ) -> Dict[str, Any]:
        """Startet Coffee-Programm - Shell koordiniert I/O.
        
        Args:
            program_key: Programm-Key (z.B. ESPRESSO_KEY)
            fill_ml: Optionale Füllmenge in ml
            program_name: Programm-Name für Response
            
        Returns:
            Dict mit status und message
            
        Raises:
            ValueError: Wenn fill_ml für Programm nicht unterstützt wird
            RuntimeError: Wenn Programm nicht gestartet werden kann
        """
        # Functional Core: Reine Funktion - Validiere Request
        validate_brew_request(program_key, program_name, fill_ml)

        # I/O: API Call - Prüfe ob Device aktiviert werden muss
        try:
            settings_data = self.client.get_settings()
            power_state = extract_power_state(settings_data)
            
            if should_activate_device(power_state):
                # I/O: API Call - Aktiviere Device
                try:
                    self.client.set_setting(
                        "BSH.Common.Setting.PowerState",
                        "BSH.Common.EnumType.PowerState.On"
                    )
                except Exception as e:
                    logger.warning(f"Error activating device: {e}")
                    # Ignoriere Fehler, versuche trotzdem zu brewen
        except Exception as e:
            logger.warning(f"Error checking device settings: {e}")
            # Ignoriere Fehler, versuche trotzdem zu brewen

        # Functional Core: Reine Funktion - Baue Options
        options = build_options(fill_ml) if fill_ml is not None else []

        # I/O: API Call - Lösche vorheriges Programm
        try:
            self.client.clear_selected_program()
        except Exception:
            # Ignoriere Fehler wenn kein Programm ausgewählt ist
            pass

        # I/O: API Call - Wähle Programm
        self.client.select_program(program_key, options=options)
        
        # I/O: API Call - Starte Programm
        self.client.start_program()

        # Functional Core: Reine Funktion - Baue Response
        result = build_brew_response(program_name, fill_ml)
        
        # I/O: DB-Zugriff - Speichere Event in History
        if self.history_manager:
            try:
                self.history_manager.add_event("program_started", {
                    "program": program_key,
                    "program_name": program_name,
                    "fill_ml": fill_ml,
                    "options": options,
                })
            except Exception as e:
                logger.warning(f"Error saving program event to history: {e}")

        return result

    def brew_espresso(self, fill_ml: int) -> Dict[str, Any]:
        """Startet Espresso - Convenience-Methode.
        
        Args:
            fill_ml: Füllmenge in ml (35-50 ml)
            
        Returns:
            Dict mit status und message
        """
        from ..core.coffee_core import ESPRESSO_KEY
        return self.brew_program(ESPRESSO_KEY, fill_ml=fill_ml, program_name="Espresso")
```

---

## 3. Tests: Functional Core (KEINE Mocks!)

```python
# tests/test_coffee_core.py
"""Tests für Functional Core - KEINE Mocks benötigt!"""

import pytest

from homeconnect_coffee.core.coffee_core import (
    build_brew_response,
    build_options,
    determine_wake_status,
    extract_operation_state,
    extract_power_state,
    should_activate_device,
    validate_brew_request,
)


class TestBuildOptions:
    """Tests für build_options() - Reine Funktion."""

    def test_build_options_with_fill_ml(self):
        """Test build_options() mit fill_ml."""
        result = build_options(50)
        assert len(result) == 1
        assert result[0]["key"] == "ConsumerProducts.CoffeeMaker.Option.FillQuantity"
        assert result[0]["value"] == 50

    def test_build_options_without_fill_ml(self):
        """Test build_options() ohne fill_ml."""
        result = build_options(None)
        assert result == []


class TestValidateBrewRequest:
    """Tests für validate_brew_request() - Reine Funktion."""

    def test_validate_brew_request_espresso_with_fill_ml(self):
        """Test validate_brew_request() mit espresso und fill_ml - OK."""
        # Sollte keine Exception werfen
        validate_brew_request("ESPRESSO_KEY", "espresso", 50)

    def test_validate_brew_request_cappuccino_with_fill_ml(self):
        """Test validate_brew_request() mit cappuccino und fill_ml - Fehler."""
        with pytest.raises(ValueError, match="does not support fill_ml"):
            validate_brew_request("CAPPUCCINO_KEY", "cappuccino", 200)

    def test_validate_brew_request_without_fill_ml(self):
        """Test validate_brew_request() ohne fill_ml - OK."""
        validate_brew_request("CAPPUCCINO_KEY", "cappuccino", None)


class TestBuildBrewResponse:
    """Tests für build_brew_response() - Reine Funktion."""

    def test_build_brew_response_with_fill_ml(self):
        """Test build_brew_response() mit fill_ml."""
        result = build_brew_response("Espresso", 50)
        assert result["status"] == "started"
        assert "Espresso (50 ml)" in result["message"]

    def test_build_brew_response_without_fill_ml(self):
        """Test build_brew_response() ohne fill_ml."""
        result = build_brew_response("Cappuccino", None)
        assert result["status"] == "started"
        assert "Cappuccino" in result["message"]
        assert "ml" not in result["message"]

    def test_build_brew_response_without_program_name(self):
        """Test build_brew_response() ohne program_name."""
        result = build_brew_response(None, 50)
        assert result["status"] == "started"
        assert "Program (50 ml)" in result["message"]


class TestDetermineWakeStatus:
    """Tests für determine_wake_status() - Reine Funktion."""

    def test_determine_wake_status_activated(self):
        """Test determine_wake_status() - Activation erfolgreich."""
        result = determine_wake_status(
            activation_successful=True,
            operation_state=None,
            power_state=None
        )
        assert result["status"] == "activated"
        assert "activated" in result["message"]

    def test_determine_wake_status_already_on_operation_state(self):
        """Test determine_wake_status() - Device bereits an (OperationState)."""
        result = determine_wake_status(
            activation_successful=False,
            operation_state="BSH.Common.EnumType.OperationState.Run",
            power_state=None
        )
        assert result["status"] == "already_on"
        assert "already activated" in result["message"]

    def test_determine_wake_status_already_on_power_state(self):
        """Test determine_wake_status() - Device bereits an (PowerState)."""
        result = determine_wake_status(
            activation_successful=False,
            operation_state=None,
            power_state="BSH.Common.EnumType.PowerState.On"
        )
        assert result["status"] == "already_on"

    def test_determine_wake_status_unknown(self):
        """Test determine_wake_status() - Status unbekannt."""
        result = determine_wake_status(
            activation_successful=False,
            operation_state="BSH.Common.EnumType.OperationState.Inactive",
            power_state="BSH.Common.EnumType.PowerState.Standby"
        )
        assert result["status"] == "unknown"
        assert "Could not determine" in result["message"]


class TestExtractOperationState:
    """Tests für extract_operation_state() - Reine Funktion."""

    def test_extract_operation_state_found(self):
        """Test extract_operation_state() - OperationState gefunden."""
        status_data = {
            "data": {
                "status": [
                    {"key": "BSH.Common.Status.OperationState", "value": "Run"}
                ]
            }
        }
        result = extract_operation_state(status_data)
        assert result == "Run"

    def test_extract_operation_state_not_found(self):
        """Test extract_operation_state() - OperationState nicht gefunden."""
        status_data = {"data": {"status": []}}
        result = extract_operation_state(status_data)
        assert result is None


class TestExtractPowerState:
    """Tests für extract_power_state() - Reine Funktion."""

    def test_extract_power_state_found(self):
        """Test extract_power_state() - PowerState gefunden."""
        settings_data = {
            "data": {
                "settings": [
                    {"key": "BSH.Common.Setting.PowerState", "value": "On"}
                ]
            }
        }
        result = extract_power_state(settings_data)
        assert result == "On"

    def test_extract_power_state_not_found(self):
        """Test extract_power_state() - PowerState nicht gefunden."""
        settings_data = {"data": {"settings": []}}
        result = extract_power_state(settings_data)
        assert result is None


class TestShouldActivateDevice:
    """Tests für should_activate_device() - Reine Funktion."""

    def test_should_activate_device_standby(self):
        """Test should_activate_device() - Device in Standby."""
        result = should_activate_device("BSH.Common.EnumType.PowerState.Standby")
        assert result is True

    def test_should_activate_device_on(self):
        """Test should_activate_device() - Device bereits an."""
        result = should_activate_device("BSH.Common.EnumType.PowerState.On")
        assert result is False

    def test_should_activate_device_none(self):
        """Test should_activate_device() - PowerState unbekannt."""
        result = should_activate_device(None)
        assert result is False
```

**Vorteile der Core-Tests:**
- ✅ **Keine Mocks** - Reine Funktionen, direkte Tests
- ✅ **Schnell** - Keine I/O-Operationen
- ✅ **Deterministisch** - Immer gleiche Ergebnisse
- ✅ **Einfach** - Klare Input/Output-Beziehungen
- ✅ **Kombinatorik** - Alle Edge Cases können getestet werden

---

## 4. Tests: Imperative Shell (Mocks für I/O)

```python
# tests/test_coffee_shell.py
"""Tests für Imperative Shell - Mocks für I/O."""

from unittest.mock import Mock, patch

import pytest

from homeconnect_coffee.shell.coffee_shell import CoffeeShell


@pytest.mark.unit
class TestCoffeeShell:
    """Tests für CoffeeShell - Shell-Tests mit Mocks."""

    def test_wake_device_activates(self, mock_client, mock_history_manager):
        """Test wake_device() - Activation erfolgreich."""
        # Mock: API Call erfolgreich
        mock_client.set_setting.return_value = {}
        
        shell = CoffeeShell(mock_client, mock_history_manager)
        result = shell.wake_device()
        
        assert result["status"] == "activated"
        mock_client.set_setting.assert_called_once()
        # Mock: History sollte Event speichern
        mock_history_manager.add_event.assert_called_once()

    def test_wake_device_already_on(self, mock_client, mock_history_manager):
        """Test wake_device() - Device bereits an."""
        # Mock: Activation fehlgeschlagen
        mock_client.set_setting.side_effect = RuntimeError("Already on")
        
        # Mock: API Calls für Status-Prüfung
        mock_client.get_status.return_value = {
            "data": {
                "status": [
                    {
                        "key": "BSH.Common.Status.OperationState",
                        "value": "BSH.Common.EnumType.OperationState.Run"
                    }
                ]
            }
        }
        mock_client.get_settings.return_value = {
            "data": {"settings": []}
        }
        
        shell = CoffeeShell(mock_client, mock_history_manager)
        result = shell.wake_device()
        
        assert result["status"] == "already_on"
        mock_client.get_status.assert_called_once()
        mock_client.get_settings.assert_called_once()

    def test_brew_program_success(self, mock_client, mock_history_manager):
        """Test brew_program() - Erfolgreich."""
        # Mock: API Calls
        mock_client.get_settings.return_value = {
            "data": {
                "settings": [
                    {
                        "key": "BSH.Common.Setting.PowerState",
                        "value": "BSH.Common.EnumType.PowerState.On"
                    }
                ]
            }
        }
        mock_client.clear_selected_program.return_value = {}
        mock_client.select_program.return_value = {}
        mock_client.start_program.return_value = {}
        
        shell = CoffeeShell(mock_client, mock_history_manager)
        result = shell.brew_program("ESPRESSO_KEY", fill_ml=50, program_name="Espresso")
        
        assert result["status"] == "started"
        assert "Espresso (50 ml)" in result["message"]
        mock_client.select_program.assert_called_once()
        mock_client.start_program.assert_called_once()
        # Mock: History sollte Event speichern
        mock_history_manager.add_event.assert_called_once()

    def test_brew_program_activates_device(self, mock_client, mock_history_manager):
        """Test brew_program() - Aktiviert Device wenn nötig."""
        # Mock: Device ist in Standby
        mock_client.get_settings.return_value = {
            "data": {
                "settings": [
                    {
                        "key": "BSH.Common.Setting.PowerState",
                        "value": "BSH.Common.EnumType.PowerState.Standby"
                    }
                ]
            }
        }
        mock_client.set_setting.return_value = {}
        mock_client.clear_selected_program.return_value = {}
        mock_client.select_program.return_value = {}
        mock_client.start_program.return_value = {}
        
        shell = CoffeeShell(mock_client, mock_history_manager)
        shell.brew_program("ESPRESSO_KEY", fill_ml=50, program_name="Espresso")
        
        # Mock: Device sollte aktiviert werden
        mock_client.set_setting.assert_called_once_with(
            "BSH.Common.Setting.PowerState",
            "BSH.Common.EnumType.PowerState.On"
        )

    def test_brew_program_invalid_fill_ml(self, mock_client, mock_history_manager):
        """Test brew_program() - ValueError für fill_ml auf unsupported program."""
        shell = CoffeeShell(mock_client, mock_history_manager)
        
        with pytest.raises(ValueError, match="does not support fill_ml"):
            shell.brew_program("CAPPUCCINO_KEY", fill_ml=200, program_name="cappuccino")
        
        # Mock: Keine API Calls sollten gemacht werden
        mock_client.select_program.assert_not_called()


@pytest.fixture
def mock_client():
    """Mock für HomeConnectClient."""
    return Mock()


@pytest.fixture
def mock_history_manager():
    """Mock für HistoryManager."""
    return Mock()
```

**Vorteile der Shell-Tests:**
- ✅ **Weniger Mocks** - Kombinatorik wird im Core getestet
- ✅ **Fokus auf I/O-Koordination** - Testet ob Shell richtig koordiniert
- ✅ **Integration** - Testet Zusammenspiel von Core und I/O

---

## 5. Handler-Anpassung

```python
# src/homeconnect_coffee/handlers/coffee_handler.py (angepasst)
"""Handler für Coffee-Operationen - Verwendet Shell."""

from typing import TYPE_CHECKING

from ..client import HomeConnectClient
from ..config import load_config
from ..shell.coffee_shell import CoffeeShell

if TYPE_CHECKING:
    from .base_handler import BaseHandler
    from ..middleware.auth_middleware import AuthMiddleware


class CoffeeHandler:
    """Handler für Coffee-Operationen."""

    @staticmethod
    def handle_wake(router: "BaseHandler", auth_middleware: "AuthMiddleware | None" = None) -> None:
        """Aktiviert Device."""
        if auth_middleware:
            if not auth_middleware.require_auth(router):
                return
        elif not router._require_auth():
            return

        try:
            # I/O: Lade Config und erstelle Client
            config = load_config()
            client = HomeConnectClient(config)
            
            # I/O: Hole HistoryManager (falls verfügbar)
            from ..handlers.history_handler import history_manager
            
            # Shell: Koordiniert I/O und ruft Core auf
            shell = CoffeeShell(client, history_manager)
            result = shell.wake_device()
            
            router._send_json(result, status_code=200)
        except Exception as e:
            CoffeeHandler._handle_error(router, e, "Error activating device")

    @staticmethod
    def handle_brew(
        router: "BaseHandler",
        fill_ml: int | None = None,
        program: str | None = None,
        auth_middleware: "AuthMiddleware | None" = None,
    ) -> None:
        """Startet Coffee-Programm."""
        # ... ähnlich wie handle_wake
        # Shell koordiniert I/O und ruft Core auf
```

---

## Zusammenfassung

### I/O-Operationen in der Shell:

1. **API Calls** (via `HomeConnectClient`):
   - `client.set_setting()` - Device aktivieren
   - `client.get_status()` - Status abrufen
   - `client.get_settings()` - Settings abrufen
   - `client.select_program()` - Programm wählen
   - `client.start_program()` - Programm starten
   - `client.clear_selected_program()` - Programm löschen

2. **DB-Zugriffe** (via `HistoryManager`):
   - `history_manager.add_event()` - Event speichern

3. **Weiteres I/O**:
   - **Logging** (`logger.warning()`, `logger.info()`) - Fehlerbehandlung
   - **Token-Datei** (indirekt via `HomeConnectClient`) - Token-Management
   - **Monitoring** (indirekt via `HomeConnectClient`) - API-Call-Tracking

### Vorteile:

✅ **Core-Tests**: Keine Mocks, schnell, deterministisch  
✅ **Shell-Tests**: Weniger Mocks, Fokus auf I/O-Koordination  
✅ **Kombinatorik**: Im Core getestet, nicht in Shell  
✅ **Wartbarkeit**: Klare Trennung von Logik und I/O  
✅ **Testbarkeit**: Core einfach zu testen, Shell isoliert testbar  

### Nächste Schritte:

1. Core-Funktionen implementieren
2. Shell-Implementierung erstellen
3. Core-Tests schreiben (ohne Mocks)
4. Shell-Tests schreiben (mit Mocks)
5. Handler anpassen
6. Schrittweise weitere Services umstrukturieren





