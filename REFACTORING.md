# Refactoring-Roadmap

## Übersicht

Diese Dokumentation identifiziert Refactoring-Potential im HomeConnect Coffee Projekt und priorisiert Verbesserungen nach Aufwand und Nutzen.

## Identifizierte Probleme

### 1. Single Responsibility Principle verletzt

**Problem:**
- `server.py` ist mit 815 Zeilen zu groß
- `CoffeeHandler` hat zu viele Verantwortlichkeiten:
  - HTTP-Request-Handling
  - Business-Logic (Wake, Brew, Status)
  - Event-Stream-Management
  - Authentifizierung
  - Dashboard-Serving

**Auswirkung:**
- Schwer zu testen
- Schwer zu warten
- Schwer zu erweitern
- Hohe Kopplung

**Lösung:**
- Aufteilen in separate Klassen:
  - `HTTPHandler` - Nur HTTP-Request-Handling
  - `CoffeeService` - Business-Logic
  - `EventStreamManager` - Event-Stream-Management
  - `AuthMiddleware` - Authentifizierung

### 2. Globale Variablen

**Problem:**
- 8 globale Variablen in `server.py`:
  - `event_clients`
  - `event_clients_lock`
  - `history_manager`
  - `event_stream_thread`
  - `event_stream_running`
  - `event_stream_stop_event`
  - `history_queue`
  - `history_worker_thread`

**Auswirkung:**
- Erschwert Testing (keine Dependency Injection möglich)
- Potenzielle Race-Conditions (trotz Locks)
- Schwer zu mocken
- Globale State macht Code unvorhersehbar

**Lösung:**
- Dependency Injection einführen
- State in Klassen kapseln
- Services als Instanzen statt globale Variablen

### 3. Fehlende Abstraktion

**Problem:**
- Business-Logic direkt im HTTP-Handler
- Keine Service-Layer
- Direkte Abhängigkeiten zu `HomeConnectClient`

**Auswirkung:**
- Business-Logic nicht wiederverwendbar
- Schwer zu testen
- Hohe Kopplung zwischen HTTP-Layer und Business-Logic

**Lösung:**
- Service-Layer einführen:
  - `CoffeeService` - Kaffeemaschinen-Operationen
  - `StatusService` - Status-Abfragen
  - `HistoryService` - History-Verwaltung

### 4. Error Handling

**Problem:**
- Inkonsistente Error-Responses
- Keine strukturierten Logs
- Fehler werden teilweise nur geloggt, nicht weitergegeben
- Keine zentrale Error-Handling-Strategie

**Auswirkung:**
- Schwer zu debuggen
- Inkonsistente API-Responses
- Fehler-Informationen könnten sensible Daten preisgeben

**Lösung:**
- Zentrale Error-Handling-Klasse
- Strukturierte Logs (z.B. mit `logging` Modul)
- Konsistente Error-Response-Format
- Error-Codes statt Fehler-Messages

### 5. Testing

**Problem:**
- Keine Unit-Tests vorhanden
- Keine Integration-Tests
- Schwer testbar durch globale Variablen

**Auswirkung:**
- Keine Regression-Tests
- Refactorings sind riskant
- Bugs werden spät entdeckt

**Lösung:**
- Unit-Tests für Core-Komponenten
- Integration-Tests für API-Endpoints
- Mock-Tests für HomeConnect API
- Test-Framework: `pytest`

### 6. Event-Stream-Worker

**Problem:**
- Läuft immer, auch wenn nicht benötigt
- Könnte optimiert werden (nur bei Bedarf starten)

**Auswirkung:**
- Unnötiger Ressourcen-Verbrauch
- Event-Stream wird auch ohne Clients gehalten

**Lösung:**
- Worker nur starten, wenn Clients verbunden sind
- Oder: Worker läuft für History-Persistierung (aktuell so implementiert)

## Refactoring-Roadmap

### Phase 1: Testing-Infrastruktur (Priorität: Hoch)

**Ziel:** Testing-Infrastruktur aufbauen, bevor größere Refactorings

**Aufwand:** 2-3 Stunden

**Schritte:**
1. `pytest` als Test-Framework einrichten
2. Test-Struktur erstellen (`tests/` Verzeichnis)
3. Erste Unit-Tests für Core-Komponenten:
   - `HomeConnectClient` (mit Mocks)
   - `TokenBundle` (Auth)
   - `HistoryManager` (SQLite)
4. CI/CD Integration (optional)

**Vorteile:**
- Regression-Tests vor Refactorings
- Sicherheit bei Änderungen
- Dokumentation durch Tests

**Abhängigkeiten:** Keine

---

### Phase 2: Service-Layer einführen (Priorität: Hoch)

**Ziel:** Business-Logic aus HTTP-Handler extrahieren

**Aufwand:** 4-6 Stunden

**Schritte:**
1. `CoffeeService` Klasse erstellen:
   - `wake_device()` - Gerät aktivieren
   - `brew_espresso(fill_ml)` - Espresso starten
   - `get_status()` - Status abrufen
2. `StatusService` Klasse erstellen:
   - `get_extended_status()` - Erweiterter Status
3. `HistoryService` Klasse erstellen:
   - `get_history()` - History abrufen
   - `get_program_counts()` - Programm-Zählungen
   - `get_daily_usage()` - Tägliche Nutzung
4. HTTP-Handler verwendet Services statt direkte Client-Calls

**Vorteile:**
- Business-Logic wiederverwendbar
- Leichter zu testen
- Klare Trennung von Concerns

**Abhängigkeiten:** Phase 1 (Testing)

**Dateien:**
- `src/homeconnect_coffee/services/coffee_service.py` (neu)
- `src/homeconnect_coffee/services/status_service.py` (neu)
- `src/homeconnect_coffee/services/history_service.py` (neu)
- `scripts/server.py` (refactored)

---

### Phase 3: Event-Stream-Manager (Priorität: Mittel)

**Ziel:** Event-Stream-Management in separate Klasse auslagern

**Aufwand:** 3-4 Stunden

**Schritte:**
1. `EventStreamManager` Klasse erstellen:
   - `start()` - Worker starten
   - `stop()` - Worker stoppen
   - `add_client()` - Client hinzufügen
   - `remove_client()` - Client entfernen
   - `broadcast_event()` - Event an alle Clients senden
2. State in Klasse kapseln (statt globale Variablen)
3. HTTP-Handler verwendet `EventStreamManager`

**Vorteile:**
- Keine globalen Variablen mehr
- Event-Stream-Management isoliert
- Leichter zu testen

**Abhängigkeiten:** Phase 1 (Testing)

**Dateien:**
- `src/homeconnect_coffee/services/event_stream_manager.py` (neu)
- `scripts/server.py` (refactored)

---

### Phase 4: Dependency Injection (Priorität: Mittel)

**Ziel:** Globale Variablen durch Dependency Injection ersetzen

**Aufwand:** 4-5 Stunden

**Schritte:**
1. `ApplicationContext` Klasse erstellen:
   - Hält alle Services und Manager
   - Wird beim Server-Start initialisiert
2. Services als Instanzen statt globale Variablen
3. HTTP-Handler erhält Context über Constructor
4. Globale Variablen entfernen

**Vorteile:**
- Keine globalen Variablen
- Leichter zu testen (Mocking möglich)
- Klare Abhängigkeiten

**Abhängigkeiten:** Phase 2, Phase 3

**Dateien:**
- `src/homeconnect_coffee/services/application_context.py` (neu)
- `scripts/server.py` (refactored)

---

### Phase 5: Error Handling verbessern (Priorität: Mittel)

**Ziel:** Zentrale Error-Handling-Strategie

**Aufwand:** 2-3 Stunden

**Schritte:**
1. `ErrorHandler` Klasse erstellen:
   - `handle_error()` - Zentrale Error-Behandlung
   - `format_error_response()` - Konsistentes Format
2. Strukturiertes Logging mit `logging` Modul
3. Error-Codes definieren
4. HTTP-Handler verwendet `ErrorHandler`

**Vorteile:**
- Konsistente Error-Responses
- Bessere Logs
- Weniger sensible Informationen in Responses

**Abhängigkeiten:** Phase 1 (Testing)

**Dateien:**
- `src/homeconnect_coffee/errors.py` (neu)
- `scripts/server.py` (refactored)

---

### Phase 6: HTTP-Handler aufteilen (Priorität: Niedrig)

**Ziel:** `CoffeeHandler` in kleinere Handler aufteilen

**Aufwand:** 3-4 Stunden

**Schritte:**
1. `BaseHandler` Klasse für gemeinsame Funktionalität
2. Spezialisierte Handler:
   - `CoffeeHandler` - Coffee-Operationen
   - `StatusHandler` - Status-Endpoints
   - `HistoryHandler` - History-Endpoints
   - `DashboardHandler` - Dashboard-Serving
3. Router für Request-Routing

**Vorteile:**
- Kleinere, fokussierte Klassen
- Leichter zu warten
- Single Responsibility Principle

**Abhängigkeiten:** Phase 2, Phase 4

**Dateien:**
- `src/homeconnect_coffee/handlers/base_handler.py` (neu)
- `src/homeconnect_coffee/handlers/coffee_handler.py` (neu)
- `src/homeconnect_coffee/handlers/status_handler.py` (neu)
- `src/homeconnect_coffee/handlers/history_handler.py` (neu)
- `src/homeconnect_coffee/handlers/dashboard_handler.py` (neu)
- `scripts/server.py` (refactored)

---

### Phase 7: Authentifizierung als Middleware (Priorität: Niedrig)

**Ziel:** Authentifizierung als Middleware-Pattern

**Aufwand:** 2-3 Stunden

**Schritte:**
1. `AuthMiddleware` Klasse erstellen
2. Middleware-Pattern implementieren
3. HTTP-Handler verwendet Middleware

**Vorteile:**
- Authentifizierung isoliert
- Leichter zu erweitern (z.B. OAuth, API-Keys)
- Testbar

**Abhängigkeiten:** Phase 4

**Dateien:**
- `src/homeconnect_coffee/middleware/auth_middleware.py` (neu)
- `scripts/server.py` (refactored)

---

## Priorisierung

### Sofort umsetzen (vor größeren Refactorings)

1. **Phase 1: Testing-Infrastruktur** ⭐⭐⭐
   - Notwendig für sichere Refactorings
   - Niedriger Aufwand, hoher Nutzen

### Kurzfristig (nächste 2-4 Wochen)

2. **Phase 2: Service-Layer** ⭐⭐⭐
   - Hoher Nutzen, mittlerer Aufwand
   - Macht Code testbarer

3. **Phase 3: Event-Stream-Manager** ⭐⭐
   - Eliminiert globale Variablen
   - Mittlerer Nutzen, mittlerer Aufwand

### Mittelfristig (nächste 1-2 Monate)

4. **Phase 4: Dependency Injection** ⭐⭐
   - Eliminiert alle globalen Variablen
   - Hoher Nutzen, mittlerer Aufwand

5. **Phase 5: Error Handling** ⭐⭐
   - Verbessert Debugging und Sicherheit
   - Mittlerer Nutzen, niedriger Aufwand

### Langfristig (optional)

6. **Phase 6: HTTP-Handler aufteilen** ⭐
   - Verbessert Wartbarkeit
   - Niedriger Nutzen, mittlerer Aufwand

7. **Phase 7: Authentifizierung als Middleware** ⭐
   - Verbessert Erweiterbarkeit
   - Niedriger Nutzen, niedriger Aufwand

## Geschätzter Gesamtaufwand

- **Phase 1:** 2-3 Stunden
- **Phase 2:** 4-6 Stunden
- **Phase 3:** 3-4 Stunden
- **Phase 4:** 4-5 Stunden
- **Phase 5:** 2-3 Stunden
- **Phase 6:** 3-4 Stunden
- **Phase 7:** 2-3 Stunden

**Gesamt:** 20-28 Stunden

## Empfehlung

**Start mit Phase 1 (Testing-Infrastruktur):**
- Notwendig für sichere Refactorings
- Niedriger Aufwand
- Sofortiger Nutzen

**Dann Phase 2 (Service-Layer):**
- Hoher Nutzen
- Macht Code testbarer
- Basis für weitere Refactorings

**Dann Phase 3 und 4 (Event-Stream-Manager + Dependency Injection):**
- Eliminiert globale Variablen
- Verbessert Testbarkeit erheblich

**Phase 5-7 sind optional:**
- Können schrittweise umgesetzt werden
- Abhängig von Bedarf und Zeit

## Risiken

### Refactoring-Risiken

1. **Breaking Changes:**
   - API-Endpoints könnten sich ändern
   - **Mitigation:** Tests verhindern Breaking Changes

2. **Bugs durch Refactoring:**
   - Neue Bugs könnten eingeführt werden
   - **Mitigation:** Umfassende Tests vor Refactoring

3. **Zeitaufwand:**
   - Refactorings dauern länger als erwartet
   - **Mitigation:** Schrittweise vorgehen, Tests nach jedem Schritt

### Abhängigkeiten

- Phase 2-7 hängen von Phase 1 ab (Testing)
- Phase 4 hängt von Phase 2 und 3 ab
- Phase 6 hängt von Phase 2 und 4 ab
- Phase 7 hängt von Phase 4 ab

## Erfolgs-Kriterien

### Nach Phase 1
- [ ] Unit-Tests für Core-Komponenten vorhanden
- [ ] Test-Coverage > 50%
- [ ] Tests laufen in CI/CD (optional)

### Nach Phase 2
- [ ] Business-Logic in Services
- [ ] HTTP-Handler verwendet Services
- [ ] Services sind testbar

### Nach Phase 4
- [ ] Keine globalen Variablen mehr
- [ ] Dependency Injection implementiert
- [ ] Alle Komponenten testbar

### Nach allen Phasen
- [ ] Code-Qualität verbessert
- [ ] Wartbarkeit erhöht
- [ ] Test-Coverage > 80%
- [ ] Keine Breaking Changes

## Zusammenfassung

Die Refactoring-Roadmap priorisiert Verbesserungen nach Aufwand und Nutzen. Start mit Testing-Infrastruktur, dann Service-Layer, dann Eliminierung globaler Variablen. Die optionalen Phasen können schrittweise umgesetzt werden.

**Empfohlener Start:** Phase 1 (Testing-Infrastruktur) → Phase 2 (Service-Layer) → Phase 3 (Event-Stream-Manager) → Phase 4 (Dependency Injection)

