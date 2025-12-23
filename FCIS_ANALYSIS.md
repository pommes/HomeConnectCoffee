# FCIS Architektur-Analyse

## Übersicht

Diese Analyse bewertet das HomeConnect Coffee Projekt hinsichtlich der **Functional Core, Imperative Shell (FCIS)** Architektur und identifiziert Ansätze zur Umstrukturierung.

## FCIS-Prinzipien

**Functional Core:**
- Reine Funktionen ohne Seiteneffekte
- Keine direkten I/O-Operationen (keine API Calls, keine DB-Zugriffe)
- Einfach testbar (deterministisch)
- Transformiert Datenstrukturen

**Imperative Shell:**
- Handhabt alle I/O-Operationen
- API Calls, DB-Zugriffe, Datei-Operationen
- Ruft Functional Core auf
- Koordiniert Seiteneffekte

## Aktuelle Architektur-Analyse

### I/O-Operationen im Code

#### 1. **HomeConnectClient** (`client.py`)
- ✅ **Gut isoliert**: Enthält nur API-Calls
- ❌ **Problem**: Wird direkt von Services aufgerufen
- **I/O-Operationen:**
  - `requests.get()`, `requests.post()`, `requests.put()`, `requests.delete()`
  - Token-Datei lesen/schreiben (`TokenBundle.from_file()`, `tokens.save()`)
  - `record_api_call()`, `record_token_refresh()` (Monitoring)

#### 2. **HistoryManager** (`history.py`)
- ✅ **Gut isoliert**: Enthält nur DB-Zugriffe
- ❌ **Problem**: Wird direkt von Services aufgerufen
- **I/O-Operationen:**
  - `sqlite3.connect()`, `cursor.execute()`
  - JSON-Datei lesen (Migration)

#### 3. **CoffeeService** (`services/coffee_service.py`)
- ❌ **Problem**: Ruft direkt `self.client.get_status()`, `self.client.set_setting()` auf
- ❌ **Problem**: Enthält Business Logic gemischt mit I/O-Aufrufen
- **Beispiel:**
  ```python
  def wake_device(self) -> Dict[str, Any]:
      # I/O direkt im Service!
      self.client.set_setting(...)
      status = self.client.get_status()  # API Call
  ```

#### 4. **StatusService** (`services/status_service.py`)
- ❌ **Problem**: Ruft direkt `self.client.get_status()`, `self.client.get_settings()` auf
- ❌ **Problem**: Liest Token-Datei direkt (`TokenBundle.from_file()`)
- ❌ **Problem**: Ruft `get_monitor()` auf (Monitoring I/O)

#### 5. **HistoryService** (`services/history_service.py`)
- ❌ **Problem**: Ruft direkt `self.history_manager.get_history()` auf
- **I/O-Operationen:** DB-Zugriffe über HistoryManager

#### 6. **EventStreamManager** (`services/event_stream_manager.py`)
- ❌ **Problem**: Macht direkte API Calls (`requests.get()` für SSE)
- ❌ **Problem**: Ruft `history_manager.add_event()` direkt auf

#### 7. **Handlers** (`handlers/`)
- ❌ **Problem**: Erstellen Services und Clients bei jedem Request neu
- ❌ **Problem**: Keine Dependency Injection
- **Beispiel:**
  ```python
  def handle_wake(router):
      config = load_config()  # I/O
      client = HomeConnectClient(config)  # I/O (Token lesen)
      coffee_service = CoffeeService(client)
      result = coffee_service.wake_device()  # I/O
  ```

## Ansätze für FCIS-Umstrukturierung

### ✅ Bereits vorhandene Ansätze

1. **Service Layer existiert bereits**
   - Business Logic ist in Services gekapselt
   - Services sind testbar (mit Mock-Objekten)
   - Klare Trennung zwischen Handlers und Services

2. **I/O-Klassen sind isoliert**
   - `HomeConnectClient` enthält nur API-Calls
   - `HistoryManager` enthält nur DB-Zugriffe
   - Beide könnten als "Shell" fungieren

3. **Statische Handler-Methoden**
   - Handlers sind bereits statisch
   - Könnten leicht Dependency Injection erhalten

### 🔄 Umstrukturierungs-Potenzial

#### **Option 1: Dependency Injection mit Interfaces**

**Functional Core:**
- Services werden zu reinen Funktionen
- Nehmen Datenstrukturen als Parameter
- Keine direkten I/O-Aufrufe

**Imperative Shell:**
- Handlers oder eine Shell-Klasse
- Ruft I/O-Klassen auf (HomeConnectClient, HistoryManager)
- Übergibt Daten an Functional Core
- Koordiniert Seiteneffekte

**Beispiel-Umstrukturierung:**

```python
# Functional Core (reine Funktionen)
def determine_wake_status(device_status: Dict, power_state: str) -> Dict[str, Any]:
    """Reine Funktion - keine I/O."""
    if power_state == "BSH.Common.EnumType.PowerState.On":
        return {"status": "already_on", "message": "Device is already activated"}
    
    op_state = device_status.get("BSH.Common.Status.OperationState")
    if op_state != "BSH.Common.EnumType.OperationState.Inactive":
        return {"status": "already_on", "message": "Device is already activated"}
    
    return {"status": "activated", "message": "Device was activated"}

# Imperative Shell
class CoffeeShell:
    def __init__(self, client: HomeConnectClient):
        self.client = client
    
    def wake_device(self) -> Dict[str, Any]:
        """Shell - koordiniert I/O und ruft Core auf."""
        try:
            # I/O: API Call
            self.client.set_setting("BSH.Common.Setting.PowerState", "BSH.Common.EnumType.PowerState.On")
            return {"status": "activated", "message": "Device was activated"}
        except RuntimeError:
            # I/O: API Calls
            status = self.client.get_status()
            settings = self.client.get_settings()
            
            # Functional Core: Reine Funktion
            return determine_wake_status(status, settings)
```

#### **Option 2: Ports & Adapters Pattern**

**Ports (Interfaces):**
- `IHomeConnectClient` - Interface für API-Calls
- `IHistoryRepository` - Interface für DB-Zugriffe

**Adapters (Implementierungen):**
- `HomeConnectClient` - Implementiert `IHomeConnectClient`
- `HistoryManager` - Implementiert `IHistoryRepository`

**Functional Core:**
- Services verwenden Interfaces (Ports)
- Keine direkten Implementierungen

**Imperative Shell:**
- Erstellt Adapter-Instanzen
- Übergibt sie an Services

#### **Option 3: Funktionale Transformationen**

**Functional Core:**
- Reine Transformationsfunktionen
- Nehmen Daten als Input, geben Daten als Output

**Imperative Shell:**
- Handler-Klassen
- Holen Daten via I/O
- Transformieren via Core
- Speichern via I/O

**Beispiel:**

```python
# Functional Core
def build_brew_response(program_name: str, fill_ml: int | None) -> Dict[str, Any]:
    """Reine Funktion - transformiert Daten."""
    if fill_ml is not None:
        message = f"{program_name} ({fill_ml} ml) is being prepared"
    else:
        message = f"{program_name} is being prepared"
    return {"status": "started", "message": message}

def validate_brew_request(program_key: str, fill_ml: int | None) -> None:
    """Reine Funktion - validiert Daten."""
    if fill_ml is not None and program_key not in PROGRAMS_WITH_FILL_ML:
        raise ValueError(f"Program does not support fill_ml option")

# Imperative Shell
class CoffeeShell:
    def brew_espresso(self, fill_ml: int) -> Dict[str, Any]:
        # I/O: API Calls
        self.client.select_program(ESPRESSO_KEY, options=build_options(fill_ml))
        self.client.start_program()
        
        # Functional Core: Reine Funktion
        return build_brew_response("Espresso", fill_ml)
```

## Konkrete Umstrukturierungs-Empfehlungen

### **Phase 1: Services zu reinen Funktionen umwandeln**

1. **CoffeeService umstrukturieren:**
   - `wake_device()` → `determine_wake_status(status_data, settings_data)`
   - `brew_program()` → `validate_brew_request()` + `build_brew_response()`
   - I/O-Aufrufe in Shell auslagern

2. **StatusService umstrukturieren:**
   - `get_status()` → Shell holt Daten, Core transformiert
   - `get_extended_status()` → Shell sammelt Daten, Core aggregiert

3. **HistoryService umstrukturieren:**
   - `get_history()` → Shell holt Daten, Core filtert/transformiert
   - `get_program_counts()` → Shell holt Daten, Core zählt

### **Phase 2: Shell-Schicht einführen**

1. **Shell-Klassen erstellen:**
   - `CoffeeShell` - Koordiniert Coffee-Operationen
   - `StatusShell` - Koordiniert Status-Abfragen
   - `HistoryShell` - Koordiniert History-Abfragen

2. **Handlers anpassen:**
   - Handlers erstellen Shell-Instanzen
   - Shell ruft I/O auf und übergibt Daten an Core

### **Phase 3: Dependency Injection**

1. **Interfaces einführen:**
   - `IHomeConnectClient` - Interface für API-Calls
   - `IHistoryRepository` - Interface für DB-Zugriffe

2. **Services anpassen:**
   - Services nehmen Interfaces als Parameter
   - Keine direkten Implementierungen

## Vorteile der FCIS-Umstrukturierung

1. **Testbarkeit:**
   - Functional Core ist einfach zu testen (reine Funktionen)
   - Keine Mock-Objekte nötig für Core-Tests
   - Shell kann isoliert getestet werden

2. **Wartbarkeit:**
   - Klare Trennung von Logik und I/O
   - Einfacher zu verstehen
   - Einfacher zu erweitern

3. **Flexibilität:**
   - I/O-Implementierungen können ausgetauscht werden
   - Core kann wiederverwendet werden
   - Shell kann verschiedene I/O-Quellen nutzen

4. **Fehlerbehandlung:**
   - I/O-Fehler werden in Shell behandelt
   - Core bleibt fehlerfrei (keine Exceptions aus I/O)

## Herausforderungen

1. **Refactoring-Aufwand:**
   - Bestehender Code muss umstrukturiert werden
   - Tests müssen angepasst werden
   - Mögliche Breaking Changes

2. **Komplexität:**
   - Mehr Abstraktionsebenen
   - Mehr Dateien/Module
   - Längere Call-Chains

3. **Performance:**
   - Mehr Funktionsaufrufe
   - Mögliche Overhead durch Abstraktion
   - (Vermutlich vernachlässigbar)

## Fazit

Das Projekt hat bereits gute Ansätze für eine FCIS-Umstrukturierung:

✅ **Service Layer existiert** - Business Logic ist gekapselt  
✅ **I/O-Klassen sind isoliert** - HomeConnectClient und HistoryManager  
✅ **Handlers sind statisch** - Leicht erweiterbar  

**Empfehlung:**
- Schrittweise Umstrukturierung in Richtung FCIS
- Beginnen mit `CoffeeService` (kleinster Service)
- Shell-Schicht einführen
- Nach und nach weitere Services umstrukturieren

Die Umstrukturierung würde die Architektur deutlich verbessern und das Projekt wartbarer und testbarer machen.





