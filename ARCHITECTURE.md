# Architektur-Dokumentation

## Übersicht

Das HomeConnect Coffee Projekt ist eine Python-Anwendung zur Steuerung von HomeConnect-Kaffeemaschinen über die offizielle HomeConnect Cloud-API. Die Anwendung besteht aus einer CLI-API, einem HTTP-Server mit Dashboard-UI und Event-Streaming-Funktionalität.

## Komponenten-Übersicht

### Core-Library (`src/homeconnect_coffee/`)

#### `client.py` - HomeConnect API Client
- **Verantwortlichkeit:** Kommunikation mit der HomeConnect API
- **Hauptfunktionen:**
  - OAuth Token-Management (automatischer Refresh)
  - API-Requests mit korrekten Headers
  - Gerätestatus, Programme, Settings abrufen
  - Programme starten/stoppen
- **Thread-Safety:** Lock für Token-Refresh verhindert Race-Conditions
- **API-Monitoring:** Jeder API-Call wird automatisch aufgezeichnet

#### `auth.py` - OAuth Token Management
- **Verantwortlichkeit:** OAuth 2.0 Authorization Code Flow
- **Hauptfunktionen:**
  - Token-Exchange (Code → Tokens)
  - Token-Refresh
  - Token-Persistierung in `tokens.json`
- **TokenBundle:** Dataclass für Token-Verwaltung mit Expiry-Check

#### `config.py` - Konfigurations-Management
- **Verantwortlichkeit:** Laden von Konfiguration aus `.env`
- **HomeConnectConfig:** Immutable Dataclass für Konfiguration
- **Umgebungsvariablen:**
  - `HOME_CONNECT_CLIENT_ID`
  - `HOME_CONNECT_CLIENT_SECRET`
  - `HOME_CONNECT_REDIRECT_URI`
  - `HOME_CONNECT_HAID`
  - `HOME_CONNECT_SCOPE`

#### `history.py` - Event-History (SQLite)
- **Verantwortlichkeit:** Persistierung von Events in SQLite-Datenbank
- **Schema:**
  - `events` Tabelle: `id`, `timestamp`, `type`, `data` (JSON)
  - Indizes auf `timestamp` und `type`
- **Features:**
  - Automatische Migration von JSON zu SQLite
  - Cursor-basierte Pagination
  - Programm-Zählungen
  - Tägliche Nutzungsstatistiken

#### `api_monitor.py` - API-Call-Monitoring
- **Verantwortlichkeit:** Tracking von API-Calls für Rate-Limit-Management
- **Features:**
  - Tägliche Statistiken mit automatischem Reset
  - Warnungen bei 80%, 95%, 100% des Limits
  - Persistierung in `api_stats.json`

### HTTP-Server (`scripts/server.py`)

#### Server-Architektur
- **Größe:** ~180 Zeilen (deutlich reduziert durch Refactoring)
- **Verantwortlichkeit:** Server-Initialisierung und Konfiguration
- **Komponenten:**
  - Initialisiert `HistoryManager`, `EventStreamManager`, `ErrorHandler`, `AuthMiddleware`
  - Konfiguriert `RequestRouter` mit Middleware und Error-Handler
  - Startet `ThreadingHTTPServer` für parallele Request-Verarbeitung

#### Request-Routing (`handlers/router.py`)

**`RequestRouter`** - Zentrale Request-Weiterleitung
- Leitet Requests an spezialisierte Handler weiter
- Verwendet `AuthMiddleware` für geschützte Endpoints
- Routing-Logik:
  - `/wake`, `/brew` → `CoffeeHandler`
  - `/status`, `/api/status` → `StatusHandler`
  - `/api/history`, `/api/stats` → `HistoryHandler`
  - `/dashboard`, `/cert`, `/health`, `/events` → `DashboardHandler`

**Endpoints:**
- `GET /cert` - SSL-Zertifikat-Download (öffentlich)
- `GET /health` - Health-Check (öffentlich)
- `GET /dashboard` - Dashboard-UI (öffentlich)
- `GET /wake` - Gerät aktivieren (authentifiziert)
- `GET /status` - Gerätestatus (authentifiziert)
- `GET /api/status` - Erweiterter Status (authentifiziert)
- `GET /api/history` - Event-History (öffentlich, nur Lesen)
- `GET /api/stats` - API-Statistiken (öffentlich, nur Lesen)
- `GET /events` - Server-Sent Events Stream (öffentlich)
- `POST /brew` - Espresso starten (authentifiziert)

#### Handler (`handlers/`)

**`BaseHandler`** - Basis-Klasse für alle Handler
- Gemeinsame Funktionalität: Authentifizierung, Error-Handling, JSON-Responses
- Request-Parsing und Token-Maskierung für Logging

**`CoffeeHandler`** - Coffee-Operationen (statische Methoden)
- `handle_wake()` - Aktiviert das Gerät
- `handle_brew()` - Startet einen Espresso
- Verwendet `CoffeeService` für Business-Logic

**`StatusHandler`** - Status-Endpoints (statische Methoden)
- `handle_status()` - Gerätestatus
- `handle_extended_status()` - Erweiterter Status mit Settings/Programmen
- Verwendet `StatusService` für Business-Logic

**`HistoryHandler`** - History-Endpoints (statische Methoden)
- `handle_history()` - Event-History mit Pagination
- `handle_api_stats()` - API-Call-Statistiken
- Verwendet `HistoryService` für Datenabfragen

**`DashboardHandler`** - Dashboard und öffentliche Endpoints (statische Methoden)
- `handle_dashboard()` - Dashboard-HTML-Serving
- `handle_cert_download()` - SSL-Zertifikat-Download
- `handle_health()` - Health-Check
- `handle_events_stream()` - Server-Sent Events Stream

#### Middleware (`middleware/`)

**`AuthMiddleware`** - Authentifizierungs-Middleware
- Token-basierte Authentifizierung (Bearer Header oder Query-Parameter)
- `check_auth()` - Prüft Authentifizierung
- `require_auth()` - Prüft und sendet 401 bei Fehler
- Callable-Interface: `middleware(router)`
- Isoliert Authentifizierungslogik für einfache Erweiterung (z.B. OAuth)

#### Services (`services/`)

**`CoffeeService`** - Business-Logic für Coffee-Operationen
- `wake_device()` - Aktiviert das Gerät
- `brew_espresso()` - Startet einen Espresso mit Füllmenge
- Kapselt HomeConnect API-Aufrufe

**`StatusService`** - Business-Logic für Status-Abfragen
- `get_status()` - Gerätestatus
- `get_extended_status()` - Erweiterter Status mit Settings/Programmen
- Kapselt HomeConnect API-Aufrufe

**`HistoryService`** - Business-Logic für History-Abfragen
- `get_history()` - Event-History mit Filterung und Pagination
- `get_program_counts()` - Programm-Zählungen
- `get_daily_usage()` - Tägliche Nutzungsstatistiken
- Kapselt SQLite-Abfragen

**`EventStreamManager`** - Event-Stream-Management
- Kapselt Event-Stream-Worker und History-Worker
- Verwaltet verbundene SSE-Clients
- `start()` / `stop()` - Startet/stoppt Worker-Threads
- `add_client()` / `remove_client()` - Client-Verwaltung
- `broadcast_event()` - Sendet Events an alle Clients
- Implementiert exponentielles Backoff bei 429-Fehlern
- Persistiert Events asynchron in SQLite

#### Error Handling (`errors.py`)

**`ErrorHandler`** - Zentralisiertes Error-Handling
- Klassifiziert Exceptions zu HTTP-Status-Codes
- Strukturierte, farbige Logging-Ausgabe
- Konsistente Error-Response-Formatierung
- `ColoredFormatter` für Terminal-Ausgabe (orange für WARNING, rot für ERROR)

### CLI-Scripts (`scripts/`)

- `start_auth_flow.py` - OAuth-Authentifizierung
- `brew_espresso.py` - Espresso starten
- `device_status.py` - Gerätestatus anzeigen
- `events.py` - Event-Stream überwachen
- `wake_device.py` - Gerät aktivieren
- `migrate_to_sqlite.py` - Manuelle Migration zu SQLite
- `export_to_json.py` - Export von SQLite zu JSON

### Frontend (`scripts/dashboard.html`)

- **Größe:** 726 Zeilen
- **Technologien:** Vanilla JavaScript, Chart.js
- **Features:**
  - Live-Status-Anzeige
  - Event-Log mit Infinite Scroll
  - Programm-Nutzung Chart
  - Tägliche Nutzung Chart
  - Server-Sent Events für Live-Updates

## Datenfluss

### Event-Stream-Flow

```
HomeConnect API
    ↓
EventStreamManager._event_stream_worker()
    ↓
history_queue (Queue)
    ↓
EventStreamManager._history_worker()
    ↓
HistoryManager.add_event()
    ↓
SQLite (history.db)
    ↓
EventStreamManager.broadcast_event()
    ↓
SSE Clients
    ↓
Dashboard (Browser)
```

### API-Request-Flow

```
HTTP Request
    ↓
RequestRouter._route_request()
    ↓
AuthMiddleware.require_auth() (wenn geschützt)
    ↓
Spezialisierter Handler (statische Methode)
    ↓
Service (CoffeeService, StatusService, etc.)
    ↓
HomeConnectClient
    ↓
HomeConnect API
    ↓
Response
```

## Threading-Modell

- **ThreadingHTTPServer:** Verarbeitet mehrere Requests gleichzeitig
- **event_stream_worker:** Daemon-Thread, läuft kontinuierlich
- **history_worker:** Daemon-Thread, verarbeitet Queue
- **Token-Refresh:** Lock verhindert Race-Conditions

## Architektur-Verbesserungen (Refactoring)

### 1. Service-Layer eingeführt
- Business-Logic in separate Service-Klassen ausgelagert
- `CoffeeService`, `StatusService`, `HistoryService` kapseln API-Aufrufe
- Handler verwenden Services statt direkter API-Calls
- Services sind isoliert testbar

### 2. Handler aufgeteilt
- Monolithischer `CoffeeHandler` (815 Zeilen) aufgeteilt in:
  - `CoffeeHandler` - Coffee-Operationen (~90 Zeilen)
  - `StatusHandler` - Status-Endpoints (~75 Zeilen)
  - `HistoryHandler` - History-Endpoints (~105 Zeilen)
  - `DashboardHandler` - Dashboard/öffentliche Endpoints (~177 Zeilen)
  - `RequestRouter` - Request-Routing (~137 Zeilen)
- Handler-Methoden sind statisch und nehmen Router als Parameter
- Keine komplexe Initialisierung mehr nötig

### 3. Event-Stream-Manager
- Event-Stream-Logik in `EventStreamManager` Klasse gekapselt
- Globale Variablen für Event-Stream entfernt
- Thread-Management zentralisiert
- Client-Verwaltung isoliert

### 4. Authentifizierung als Middleware
- `AuthMiddleware` kapselt Authentifizierungslogik
- Isoliert und einfach erweiterbar (z.B. OAuth, API-Keys)
- Handler verwenden Middleware optional (Rückwärtskompatibilität)

### 5. Zentralisiertes Error-Handling
- `ErrorHandler` für konsistente Error-Responses
- Strukturiertes, farbiges Logging
- Exception-Klassifizierung zu HTTP-Status-Codes

### 6. Testing-Infrastruktur
- `pytest` für Unit-Tests
- 109 Tests mit >66% Code-Coverage
- Services, Handler, Middleware isoliert testbar

## Abhängigkeiten

### Externe Bibliotheken
- `requests` - HTTP-Requests
- `sseclient` - Server-Sent Events Client
- `python-dotenv` - .env Datei-Laden
- `sqlite3` - SQLite-Datenbank (Standard-Library)

### Python-Version
- Python 3.11+

## Performance-Überlegungen

### Optimierungen
- SQLite statt JSON für History (O(1) INSERT statt O(n))
- Asynchrones Event-Speichern über Queue
- ThreadingHTTPServer für parallele Requests
- Cursor-basierte Pagination für große Event-Listen
- Service-Layer ermöglicht Caching und Optimierungen

### Potenzielle Bottlenecks
- Event-Stream-Worker läuft kontinuierlich für Event-Persistierung
- Keine Connection-Pooling für HomeConnect API
- SQLite kann bei sehr hoher Last limitiert sein (für Raspberry Pi Zero ausreichend)

## Code-Statistiken

### Nach Refactoring
- `server.py`: ~180 Zeilen (vorher: 815 Zeilen)
- Handler gesamt: ~600 Zeilen (aufgeteilt in 5 Dateien)
- Services: ~260 Zeilen (4 Service-Klassen)
- Middleware: ~96 Zeilen (1 Middleware-Klasse)
- Error-Handling: ~338 Zeilen (1 ErrorHandler-Klasse)
- Tests: 109 Unit-Tests mit >66% Code-Coverage

### Verbesserungen
- **Single Responsibility**: Jede Klasse hat eine klare Verantwortlichkeit
- **Testbarkeit**: Alle Komponenten isoliert testbar
- **Wartbarkeit**: Kleinere, fokussierte Dateien
- **Erweiterbarkeit**: Middleware-Pattern ermöglicht einfache Erweiterungen

