# Sicherheits-Analyse

## Übersicht

Diese Dokumentation analysiert die Sicherheitsaspekte des HomeConnect Coffee Projekts und identifiziert potenzielle Risiken sowie Best Practices.

## Identifizierte Sicherheitsrisiken

### 🔴 Kritisch

#### 1. Token in URL-Parametern
**Risiko:** Tokens werden in URL-Parametern akzeptiert (`?token=...`)

**Problem:**
- Tokens können in Server-Logs, Browser-History, Referrer-Headers landen
- Tokens werden zwar im Log maskiert (`__MASKED__`), aber nur für die Anzeige
- Tokens können durch Logs, Browser-Cache, Proxy-Logs kompromittiert werden

**Aktueller Status:**
- ✅ Token-Maskierung im Log implementiert
- ⚠️ Token werden trotzdem in URL-Parametern akzeptiert
- ⚠️ Keine Warnung bei Verwendung von URL-Parametern

**Empfehlung:**
- Token nur im Authorization-Header akzeptieren
- URL-Parameter als deprecated markieren und entfernen
- Oder: Warnung bei Verwendung von URL-Parametern ausgeben

#### 2. CORS: Access-Control-Allow-Origin: *
**Risiko:** Wildcard-CORS erlaubt Zugriff von jeder Domain

**Problem:**
- Jede Website kann Requests an den Server senden
- Potenzielle CSRF-Angriffe möglich
- Sensible Daten könnten von fremden Websites abgerufen werden

**Aktueller Status:**
- ⚠️ Alle Endpoints senden `Access-Control-Allow-Origin: *`
- ⚠️ Keine CORS-Konfiguration

**Empfehlung:**
- CORS auf spezifische Domains beschränken
- Oder: CORS nur für öffentliche Endpoints (`/dashboard`, `/api/history`, `/api/stats`)
- Geschützte Endpoints sollten keine CORS-Header senden

#### 3. Keine Rate-Limiting auf Server-Seite
**Risiko:** Keine Begrenzung der Request-Anzahl pro IP/Token

**Problem:**
- Potenzielle DoS-Angriffe möglich
- Unbegrenzte API-Calls können HomeConnect Rate-Limit überschreiten
- Keine Schutzmaßnahmen gegen Brute-Force-Angriffe

**Aktueller Status:**
- ⚠️ Keine Rate-Limiting-Implementierung
- ✅ HomeConnect API hat eigenes Rate-Limit (1000 Calls/Tag)
- ✅ API-Monitoring vorhanden, aber keine Blockierung

**Empfehlung:**
- Rate-Limiting pro IP-Adresse implementieren
- Rate-Limiting pro Token implementieren
- Exponential Backoff bei zu vielen Requests

### 🟡 Mittel

#### 4. Input-Validierung unvollständig
**Risiko:** Eingaben werden nicht vollständig validiert

**Aktueller Status:**
- ✅ `fill_ml` wird validiert (nur Integer, Default 50)
- ⚠️ Keine Range-Validierung (35-50 ml)
- ⚠️ Query-Parameter werden nicht vollständig validiert
- ⚠️ JSON-Body wird nicht validiert (nur `json.loads()`)

**Beispiel:**
```python
# scripts/server.py:166
fill_ml = int(fill_ml_param) if fill_ml_param and fill_ml_param.isdigit() else 50
# Keine Prüfung auf 35-50 ml Range!
```

**Empfehlung:**
- Range-Validierung für `fill_ml` (35-50 ml)
- Validierung aller Query-Parameter
- JSON-Schema-Validierung für POST-Requests
- Sanitization von User-Input

#### 5. Fehler-Informationen zu detailliert
**Risiko:** Fehlermeldungen könnten sensible Informationen preisgeben

**Aktueller Status:**
- ⚠️ Fehlermeldungen enthalten manchmal Stack-Traces
- ⚠️ API-Fehler werden direkt an Client weitergegeben
- ✅ Token werden nicht in Fehlermeldungen ausgegeben

**Beispiel:**
```python
# scripts/server.py:152
self._send_error(500, f"Fehler beim Initialisieren: {str(e)}")
# Könnte interne Fehlerdetails preisgeben
```

**Empfehlung:**
- Generische Fehlermeldungen für Clients
- Detaillierte Fehler nur im Server-Log
- Fehler-Codes statt Fehler-Messages

#### 6. Selbstsigniertes SSL-Zertifikat
**Risiko:** Selbstsignierte Zertifikate werden von Browsern nicht vertrauenswürdig eingestuft

**Aktueller Status:**
- ✅ Zertifikat-Generierung implementiert
- ✅ Zertifikat-Installation dokumentiert
- ⚠️ Benutzer müssen Zertifikat manuell als vertrauenswürdig markieren
- ⚠️ Zertifikat-Ablauf nicht automatisch erneuert

**Empfehlung:**
- Zertifikat-Ablauf überwachen
- Automatische Erneuerung vor Ablauf
- Oder: Let's Encrypt für Produktionsumgebung

### 🟢 Niedrig

#### 7. Secrets-Management
**Risiko:** Secrets werden in Dateien gespeichert

**Aktueller Status:**
- ✅ `.env` und `tokens.json` sind in `.gitignore`
- ✅ Secrets werden nicht in Git committed
- ⚠️ Secrets werden im Klartext gespeichert
- ⚠️ Keine Verschlüsselung für `tokens.json`

**Empfehlung:**
- Verschlüsselung für `tokens.json` (optional)
- Secrets-Rotation-Strategie
- Oder: Secrets-Management-Service (z.B. HashiCorp Vault)

#### 8. Keine Request-Size-Limits
**Risiko:** Große Requests könnten Server überlasten

**Aktueller Status:**
- ⚠️ Keine Begrenzung der Request-Größe
- ⚠️ JSON-Body wird komplett in Memory geladen

**Empfehlung:**
- Max Request-Size definieren (z.B. 1 MB)
- Streaming für große Bodies

#### 9. Keine Authentifizierung für öffentliche Endpoints
**Risiko:** Öffentliche Endpoints könnten missbraucht werden

**Aktueller Status:**
- ✅ `/dashboard`, `/api/history`, `/api/stats` sind öffentlich (nur Lesen)
- ⚠️ Keine Rate-Limiting für öffentliche Endpoints
- ⚠️ Keine IP-basierte Zugriffskontrolle

**Empfehlung:**
- Rate-Limiting für öffentliche Endpoints
- Optional: IP-Whitelist für sensible Endpoints

## Best Practices (bereits implementiert)

### ✅ Implementiert

1. **Token-Maskierung in Logs**
   - Tokens werden in Logs als `__MASKED__` angezeigt
   - Verhindert versehentliche Token-Exposition

2. **HTTPS-Support**
   - SSL/TLS für verschlüsselte Verbindungen
   - Zertifikat-Generierung und Installation dokumentiert

3. **Secrets in .gitignore**
   - `.env`, `tokens.json`, `api_stats.json` sind ausgeschlossen
   - Verhindert versehentliches Committen von Secrets

4. **Thread-Safe Token-Refresh**
   - Lock verhindert Race-Conditions beim Token-Refresh
   - Verhindert doppelte Token-Refresh-Requests

5. **Input-Validierung (teilweise)**
   - `fill_ml` wird auf Integer geprüft
   - Query-Parameter werden geparst und validiert

6. **Error-Handling**
   - Exceptions werden abgefangen
   - Keine Stack-Traces werden an Clients gesendet (meistens)

## Empfohlene Verbesserungen

### Priorität 1 (Hoch)

1. **CORS einschränken**
   - Wildcard-CORS entfernen
   - Nur spezifische Domains erlauben
   - Oder: CORS nur für öffentliche Endpoints

2. **Token nur im Header akzeptieren**
   - URL-Parameter als deprecated markieren
   - Warnung bei Verwendung von URL-Parametern
   - Langfristig: URL-Parameter entfernen

3. **Rate-Limiting implementieren**
   - Pro IP-Adresse
   - Pro Token
   - Exponential Backoff

### Priorität 2 (Mittel)

4. **Input-Validierung verbessern**
   - Range-Validierung für `fill_ml` (35-50 ml)
   - JSON-Schema-Validierung
   - Sanitization von User-Input

5. **Fehler-Informationen reduzieren**
   - Generische Fehlermeldungen für Clients
   - Detaillierte Fehler nur im Log
   - Fehler-Codes statt Messages

6. **Request-Size-Limits**
   - Max Request-Size definieren
   - Streaming für große Bodies

### Priorität 3 (Niedrig)

7. **Secrets-Verschlüsselung**
   - Optional: Verschlüsselung für `tokens.json`
   - Secrets-Rotation-Strategie

8. **Zertifikat-Management**
   - Zertifikat-Ablauf überwachen
   - Automatische Erneuerung

9. **IP-Whitelist (optional)**
   - Für sensible Endpoints
   - Konfigurierbar über `.env`

## Sicherheits-Checkliste

### Vor Produktionseinsatz

- [ ] CORS auf spezifische Domains beschränken
- [ ] Token nur im Authorization-Header akzeptieren
- [ ] Rate-Limiting implementieren
- [ ] Input-Validierung vollständig implementieren
- [ ] Fehler-Informationen reduzieren
- [ ] Request-Size-Limits definieren
- [ ] Zertifikat-Ablauf überwachen
- [ ] Secrets-Rotation-Strategie definieren
- [ ] Security-Headers hinzufügen (HSTS, CSP, etc.)
- [ ] Penetration-Testing durchführen

### Für Entwicklung

- [ ] `.env` und `tokens.json` sind in `.gitignore`
- [ ] Keine Secrets in Code committed
- [ ] HTTPS für lokale Entwicklung
- [ ] Token-Maskierung in Logs aktiviert

## Weitere Überlegungen

### Für Raspberry Pi Zero (Produktionsumgebung)

- **Resource-Limits:** Rate-Limiting ist besonders wichtig
- **Monitoring:** API-Call-Monitoring bereits implementiert
- **Logging:** Strukturiertes Logging für bessere Analyse
- **Backup:** Secrets und History regelmäßig sichern

### Compliance

- **DSGVO:** Event-History könnte personenbezogene Daten enthalten
- **Logging:** IP-Adressen werden geloggt (DSGVO-relevant)
- **Datenaufbewahrung:** History sollte automatisch bereinigt werden (optional)

## Zusammenfassung

Das Projekt implementiert grundlegende Sicherheitsmaßnahmen (HTTPS, Token-Maskierung, Secrets-Management), hat aber noch Verbesserungspotential in den Bereichen CORS, Rate-Limiting und Input-Validierung. Für eine Produktionsumgebung sollten die Priorität-1-Verbesserungen umgesetzt werden.

