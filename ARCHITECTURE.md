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

#### `CoffeeHandler` - HTTP Request Handler
- **Größe:** 815 Zeilen (zu groß - Single Responsibility verletzt)
- **Verantwortlichkeiten:**
  - HTTP-Request-Handling
  - Authentifizierung
  - Business-Logic (Wake, Brew, Status)
  - Event-Stream-Management
  - Dashboard-Serving

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

#### Globale Variablen (Problem)
- `event_clients` - Liste verbundener SSE-Clients
- `event_clients_lock` - Lock für Thread-Safety
- `history_manager` - HistoryManager-Instanz
- `event_stream_thread` - Event-Stream-Worker Thread
- `event_stream_running` - Flag für Worker-Status
- `event_stream_stop_event` - Event zum Stoppen des Workers
- `history_queue` - Queue für asynchrones Event-Speichern
- `history_worker_thread` - History-Worker Thread

#### Worker-Threads

**`event_stream_worker()`:**
- Läuft kontinuierlich für Event-Persistierung
- Verbindet mit HomeConnect Events-API
- Speichert Events asynchron in History-Queue
- Sendet Events an verbundene SSE-Clients
- Implementiert exponentielles Backoff bei 429-Fehlern

**`history_worker()`:**
- Verarbeitet Events aus der Queue
- Speichert Events in SQLite-Datenbank
- Läuft asynchron, blockiert nicht den Haupt-Thread

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
event_stream_worker()
    ↓
history_queue (Queue)
    ↓
history_worker()
    ↓
SQLite (history.db)
    ↓
event_clients (SSE)
    ↓
Dashboard (Browser)
```

### API-Request-Flow

```
HTTP Request
    ↓
CoffeeHandler.do_GET() / do_POST()
    ↓
_check_auth() (wenn benötigt)
    ↓
load_config() + HomeConnectClient()
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

## Identifizierte Probleme

### 1. Single Responsibility Principle verletzt
- `server.py` ist mit 815 Zeilen zu groß
- `CoffeeHandler` hat zu viele Verantwortlichkeiten:
  - HTTP-Handling
  - Business-Logic
  - Event-Stream-Management
  - Authentifizierung

### 2. Globale Variablen
- 8 globale Variablen in `server.py`
- Erschwert Testing und Dependency Injection
- Potenzielle Race-Conditions (trotz Locks)

### 3. Fehlende Abstraktion
- Business-Logic direkt im HTTP-Handler
- Keine Service-Layer
- Direkte Abhängigkeiten zu HomeConnectClient

### 4. Error Handling
- Inkonsistente Error-Responses
- Keine strukturierten Logs
- Fehler werden teilweise nur geloggt, nicht weitergegeben

### 5. Testing
- Keine Unit-Tests vorhanden
- Keine Integration-Tests
- Schwer testbar durch globale Variablen

### 6. Event-Stream-Worker
- Läuft immer, auch wenn nicht benötigt
- Könnte optimiert werden (nur bei Bedarf starten)

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

### Potenzielle Bottlenecks
- Event-Stream-Worker läuft immer (auch ohne Clients)
- Globale Locks könnten bei hoher Last problematisch sein
- Keine Connection-Pooling für HomeConnect API

