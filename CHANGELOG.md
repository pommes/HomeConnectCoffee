# Changelog

Alle bemerkenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

## [1.1.0] - 2025-11-28

### Added

#### Architektur-Refactoring
- **Service-Layer** eingeführt für Business-Logic-Isolation
  - **Commit:** [`1d1fd07`](https://github.com/pommes/HomeConnectCoffee/commit/1d1fd07)
  - `CoffeeService` - Kapselt Coffee-Operationen (Wake, Brew)
  - `StatusService` - Kapselt Status-Abfragen
  - `HistoryService` - Kapselt History-Abfragen
  - Services sind isoliert testbar und wiederverwendbar

- **Handler-Aufteilung** für bessere Wartbarkeit
  - **Commit:** [`87fafce`](https://github.com/pommes/HomeConnectCoffee/commit/87fafce)
  - Monolithischer `CoffeeHandler` (815 Zeilen) aufgeteilt in:
    - `CoffeeHandler` - Coffee-Operationen (~90 Zeilen)
    - `StatusHandler` - Status-Endpoints (~75 Zeilen)
    - `HistoryHandler` - History-Endpoints (~105 Zeilen)
    - `DashboardHandler` - Dashboard/öffentliche Endpoints (~177 Zeilen)
    - `RequestRouter` - Request-Routing (~137 Zeilen)
  - Handler-Methoden sind statisch und nehmen Router als Parameter
  - Keine komplexe Initialisierung mehr nötig

- **EventStreamManager** für Event-Stream-Management
  - **Commit:** [`aa7eab6`](https://github.com/pommes/HomeConnectCoffee/commit/aa7eab6)
  - Kapselt Event-Stream-Worker und History-Worker
  - Verwaltet verbundene SSE-Clients
  - Thread-Management zentralisiert
  - Globale Variablen für Event-Stream entfernt

- **AuthMiddleware** für Authentifizierung
  - **Commit:** [`da01a61`](https://github.com/pommes/HomeConnectCoffee/commit/da01a61)
  - Token-basierte Authentifizierung isoliert
  - Einfach erweiterbar (z.B. OAuth, API-Keys)
  - Callable-Interface: `middleware(router)`
  - Rückwärtskompatibel mit Legacy-Authentifizierung

- **ErrorHandler** für zentralisiertes Error-Handling
  - **Commit:** [`a8fc20e`](https://github.com/pommes/HomeConnectCoffee/commit/a8fc20e)
  - Konsistente Error-Response-Formatierung
  - Strukturiertes, farbiges Logging (orange für WARNING, rot für ERROR)
  - Exception-Klassifizierung zu HTTP-Status-Codes
  - `ColoredFormatter` für Terminal-Ausgabe mit Terminal-Erkennung

- **Testing-Infrastruktur** mit pytest
  - **Commit:** [`40ac511`](https://github.com/pommes/HomeConnectCoffee/commit/40ac511)
  - 109 Unit-Tests mit >66% Code-Coverage
  - Tests für Services, Handler, Middleware, Error-Handling
  - Mock-basierte Tests für isolierte Komponenten

### Changed

- **Server-Architektur** komplett refactored
  - `server.py` von 815 auf ~180 Zeilen reduziert
  - Single Responsibility Principle durchgesetzt
  - Globale Variablen weitgehend eliminiert
  - Dependency Injection für bessere Testbarkeit

- **Handler-Initialisierung** vereinfacht
  - Statische Handler-Methoden statt komplexer Instanziierung
  - Keine `_skip_auto_handle` Logik mehr nötig
  - Direkte Methodenaufrufe statt Attribut-Kopie

- **Authentifizierung** als Middleware-Pattern
  - Handler akzeptieren optionalen `auth_middleware` Parameter
  - Legacy-Methode `router._require_auth()` bleibt verfügbar

### Fixed

- Komplexe Handler-Initialisierung mit `_skip_auto_handle` entfernt
- Manuelle Attribut-Kopie zwischen Router und Handlern entfernt
- Tight Coupling zwischen Router und Handler-Klassen reduziert

## [1.0.0] - 2025-11-28

### Added

#### API-Monitoring und Rate-Limit-Optimierung
- **Commit:** [`d2b9420`](https://github.com/pommes/HomeConnectCoffee/commit/d2b9420)
- API-Call-Monitoring-System implementiert (`api_monitor.py`)
- Tägliche API-Call-Statistiken mit automatischem Reset
- Warnungen bei 80%, 95% und 100% des Tageslimits (1000 Calls)
- HTTP-Endpoint `/api/stats` für Statistiken
- Event-Stream statt periodischem Polling im Dashboard
- Reduzierung von ~5.760 API Calls/Tag auf ~2-5 Calls pro Seitenaufruf
- Exponentielles Backoff bei 429 Rate-Limit-Fehlern
- Retry-After Header Support für Rate-Limit-Handling

#### Lazy Loading für Event-History
- **Commit:** [`0993e12`](https://github.com/pommes/HomeConnectCoffee/commit/0993e12)
- Infinite Scroll für Event-Log im Dashboard
- Cursor-basierte Pagination mit `before_timestamp` Parameter
- Initial Load: 20 Events statt 50 für schnellere Ladezeit
- Automatisches Nachladen beim Scrollen nach unten
- Neueste Events werden oben angezeigt
- Loading-Indikator während des Nachladens

#### SQLite Migration für Event-History
- **Commit:** [`1e4506d`](https://github.com/pommes/HomeConnectCoffee/commit/1e4506d)
- Migration von JSON zu SQLite für bessere Performance
- Automatische Migration beim ersten Start
- Indizes auf `timestamp` und `type` für effiziente Queries
- O(1) INSERT statt O(n) bei JSON (nur neues Event wird geschrieben)
- Export-Script `export_to_json.py` für Backups
- Migration-Script `migrate_to_sqlite.py` für manuelle Migration
- Makefile-Targets: `make migrate_history` und `make export_history`
- Reduzierung von 5.5 MB geschriebenen Daten/Stunde auf nur neue Events

#### Dashboard UI mit Event-Stream und Persistierung
- **Commit:** [`b29a93c`](https://github.com/pommes/HomeConnectCoffee/commit/b29a93c)
- Dashboard HTML-Interface (`/dashboard`)
- Server-Sent Events (SSE) für Live-Updates
- Event-Persistierung in History-Datenbank
- Reload-Funktionalität: Events bleiben nach Seiten-Reload erhalten
- Live-Status-Anzeige (Power State, Operation State)
- Aktives Programm-Anzeige
- Programm-Nutzung Chart (Bar Chart)
- Tägliche Nutzung Chart (Line Chart, letzte 7 Tage)
- Event-Log mit Live-Events
- ThreadingHTTPServer für gleichzeitige Request-Verarbeitung

#### Token-Authentifizierung und TLS
- **Commit:** [`200c338`](https://github.com/pommes/HomeConnectCoffee/commit/200c338)
- Token-basierte Authentifizierung für API-Endpoints
- Bearer Token im Authorization-Header
- Token als URL-Parameter (mit Maskierung im Log)
- SSL-Zertifikat-Generierung (`make cert`)
- Selbstsigniertes Zertifikat für `localhost`, `*.local` und `elias.local`
- HTTPS-Support für sichere Verbindungen
- Zertifikat-Installation im Mac Schlüsselbund (`make cert_install`)
- Zertifikat-Export für iOS-Installation (`make cert_export`)
- Zertifikat-Download-Endpoint `/cert` für Browser-Download

#### HTTP-Server für Siri Shortcuts Integration
- **Commit:** [`c43e560`](https://github.com/pommes/HomeConnectCoffee/commit/c43e560)
- HTTP-Server für iOS/iPadOS Zugriff
- Endpoints:
  - `GET /wake` - Aktiviert das Gerät
  - `GET /status` - Zeigt den Gerätestatus
  - `GET /api/status` - Erweiterter Status (Settings, Programme)
  - `POST /brew` - Startet einen Espresso
  - `GET /health` - Health-Check
- Shell-Scripts für Siri Shortcuts (`wake.sh`, `brew.sh`)
- Request-Logging mit Token-Maskierung
- CORS-Header für Cross-Origin-Requests

#### Basis CLI API und Makefile
- **Commit:** [`9448183`](https://github.com/pommes/HomeConnectCoffee/commit/9448183)
- Initiale Projektstruktur
- HomeConnect API Integration
- OAuth 2.0 Authorization Code Flow
- CLI-Scripts:
  - `start_auth_flow.py` - OAuth-Authentifizierung
  - `brew_espresso.py` - Espresso starten
  - `device_status.py` - Gerätestatus abrufen
  - `events.py` - Event-Stream überwachen
  - `wake_device.py` - Gerät aktivieren
- Makefile mit Targets: `init`, `auth`, `brew`, `status`, `events`, `wake`
- Token-Refresh-Mechanismus
- Konfiguration über `.env` Datei

### Changed

- Event-Stream-Worker läuft kontinuierlich für Event-Persistierung
- Dashboard verwendet Event-Stream statt periodischem Polling
- History-Speicherung von JSON zu SQLite migriert
- API-Call-Monitoring für besseres Rate-Limit-Management

### Fixed

- Server-Blocking-Problem durch Umstellung auf ThreadingHTTPServer
- Event-Parsing für Programm-Events korrigiert
- Tägliche Nutzung-Berechnung mit korrekter Monatsübergang-Behandlung
- Token-Refresh-Race-Conditions durch Lock-Mechanismus behoben
- BrokenPipeError bei SSE-Client-Disconnects abgefangen

### Security

- Token-Maskierung in Logs implementiert
- SSL/TLS für sichere Verbindungen
- Token-basierte Authentifizierung für geschützte Endpoints
- Secrets in `.env` und `tokens.json` (nicht in Git)

[Unreleased]: https://github.com/pommes/HomeConnectCoffee/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/pommes/HomeConnectCoffee/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/pommes/HomeConnectCoffee/compare/9448183...d2b9420

