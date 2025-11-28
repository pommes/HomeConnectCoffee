# Changelog

Alle bemerkenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

## [1.0.0] - 2025-11-28

### Added

#### API-Monitoring und Rate-Limit-Optimierung
- **Commit:** [`d2b9420`](https://github.com/tim/HomeConnectCoffee/commit/d2b9420)
- API-Call-Monitoring-System implementiert (`api_monitor.py`)
- Tägliche API-Call-Statistiken mit automatischem Reset
- Warnungen bei 80%, 95% und 100% des Tageslimits (1000 Calls)
- HTTP-Endpoint `/api/stats` für Statistiken
- Event-Stream statt periodischem Polling im Dashboard
- Reduzierung von ~5.760 API Calls/Tag auf ~2-5 Calls pro Seitenaufruf
- Exponentielles Backoff bei 429 Rate-Limit-Fehlern
- Retry-After Header Support für Rate-Limit-Handling

#### Lazy Loading für Event-History
- **Commit:** [`0993e12`](https://github.com/tim/HomeConnectCoffee/commit/0993e12)
- Infinite Scroll für Event-Log im Dashboard
- Cursor-basierte Pagination mit `before_timestamp` Parameter
- Initial Load: 20 Events statt 50 für schnellere Ladezeit
- Automatisches Nachladen beim Scrollen nach unten
- Neueste Events werden oben angezeigt
- Loading-Indikator während des Nachladens

#### SQLite Migration für Event-History
- **Commit:** [`1e4506d`](https://github.com/tim/HomeConnectCoffee/commit/1e4506d)
- Migration von JSON zu SQLite für bessere Performance
- Automatische Migration beim ersten Start
- Indizes auf `timestamp` und `type` für effiziente Queries
- O(1) INSERT statt O(n) bei JSON (nur neues Event wird geschrieben)
- Export-Script `export_to_json.py` für Backups
- Migration-Script `migrate_to_sqlite.py` für manuelle Migration
- Makefile-Targets: `make migrate_history` und `make export_history`
- Reduzierung von 5.5 MB geschriebenen Daten/Stunde auf nur neue Events

#### Dashboard UI mit Event-Stream und Persistierung
- **Commit:** [`b29a93c`](https://github.com/tim/HomeConnectCoffee/commit/b29a93c)
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
- **Commit:** [`200c338`](https://github.com/tim/HomeConnectCoffee/commit/200c338)
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
- **Commit:** [`c43e560`](https://github.com/tim/HomeConnectCoffee/commit/c43e560)
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
- **Commit:** [`9448183`](https://github.com/tim/HomeConnectCoffee/commit/9448183)
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

[Unreleased]: https://github.com/tim/HomeConnectCoffee/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/tim/HomeConnectCoffee/compare/9448183...d2b9420

