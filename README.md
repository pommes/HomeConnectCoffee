# HomeConnect Coffee Steuerung

Dieses Projekt zeigt, wie du deine Bosch CTL7181B0 (und andere HomeConnect-Kaffeemaschinen) per Python-Skript über die offizielle HomeConnect-Cloud-API starten kannst.

## Voraussetzungen

1. **HomeConnect-Entwicklerkonto** auf [developer.home-connect.com](https://developer.home-connect.com)
2. **OAuth-Client** (Typ *Server Application*) mit Redirect-URL `http://localhost:3000/callback` oder ähnlich
3. **Gerät verknüpft** (über die HomeConnect-App)
4. Python 3.11+

## Einrichtung

### 1. Application bei Home Connect registrieren

1. Gehe zu [developer.home-connect.com/applications](https://developer.home-connect.com/applications)
2. Klicke auf **"Register Application"** oder **"New Application"**
3. Fülle das Formular aus:
   - **Application ID**: z.B. "HomeConnect Coffee Control"
   - **OAuth Flow**: Wähle **"Authorization Code Grant flow"** (nicht "Device Flow")
   - **Home Connect User Account for Testing**: **Leer lassen** – Wenn du den Account in deinem Profil gesetzt hast (E-Mail-Adresse), wird dieser automatisch verwendet. Nur ausfüllen, wenn du einen anderen Test-Account für diese spezifische Application verwenden möchtest.
   - **Redirect URI**: `http://localhost:3000/callback`
   - **Scopes**: Werden beim Auth-Flow angefordert (nicht bei der Registrierung) – siehe `.env` Datei
   - **Add additional redirect URIs**: Optional – nur aktivieren, wenn du mehrere Redirect URIs benötigst (z.B. für verschiedene Umgebungen)
   - **Enable One Time Token Mode**: **NICHT aktivieren** – Diese Option würde verhindern, dass Refresh Tokens mehrfach verwendet werden können. Das Projekt nutzt Refresh Tokens automatisch zur Token-Erneuerung.
   - **Sync to China**: Nur aktivieren, wenn du die Application in China verwenden möchtest
   
   **Hinweis:** Der Application Type wird automatisch basierend auf dem gewählten OAuth Flow bestimmt (bei Authorization Code Grant ist das "Server Application").
4. Nach dem Speichern erhältst du:
   - **Client ID** (sichtbar in der Übersicht)
   - **Client Secret** (wird nur einmal angezeigt – **sofort kopieren und sicher speichern!**)

### 2. Lokale Umgebung einrichten

```bash
cd /Users/tim/Development/HomeConnectCoffee
make init  # oder manuell: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### 3. .env Datei erstellen und ausfüllen

Erstelle eine `.env` Datei im Projektverzeichnis mit folgendem Inhalt:

```bash
HOME_CONNECT_CLIENT_ID=deine-client-id-hier
HOME_CONNECT_CLIENT_SECRET=dein-client-secret-hier
HOME_CONNECT_REDIRECT_URI=http://localhost:3000/callback
HOME_CONNECT_HAID=
HOME_CONNECT_SCOPE=IdentifyAppliance Control CoffeeMaker Settings Monitor
```

**Wichtig:**
- Trage die **Client ID** und das **Client Secret** aus Schritt 1 ein (aus der Application-Übersicht kopieren)
- Die **HAID** (Home Appliance ID) lässt du zunächst leer – diese findest du nach dem ersten Auth-Flow heraus (siehe nächster Schritt)
- Die **Redirect URI** muss exakt mit der in der Application-Registrierung übereinstimmen
- Die **Scopes** werden beim Auth-Flow angefordert (nicht bei der Application-Registrierung). Die hier angegebenen Scopes werden in der Authorization-URL verwendet.

### 4. HAID herausfinden (nach erstem Auth-Flow)

Die HAID findest du nach erfolgreicher Authentifizierung:

1. Führe den Auth-Flow aus (siehe nächster Abschnitt)
2. Danach kannst du mit `make status` oder `python -m scripts.device_status` alle registrierten Geräte anzeigen
3. Die HAID steht im JSON-Output unter `data.homeappliances[].haid`
4. Trage diese HAID in deine `.env` Datei ein

## Autorisierung anstoßen

```bash
make auth
```

oder

```bash
make auth AUTH_ARGS="--open-browser"
```

Der Befehl öffnet (bzw. zeigt) die Authorize-URL. Nach Login erhältst du einen `code`, den du ins Terminal kopierst. Das Skript speichert `tokens.json` mit Access- und Refresh-Token.

**Tipp:** Mit `--open-browser` öffnet sich der Browser automatisch. Mit `--code "DEIN_CODE"` kannst du den Code direkt als Argument übergeben.

## Gerät aktivieren

Wenn das Gerät im Standby-Modus ist, kannst du es per API aktivieren:

```bash
make wake
```

Das Skript prüft den PowerState und aktiviert das Gerät automatisch, falls es im Standby ist.

## Espresso starten

Das `make brew` Kommando aktiviert das Gerät automatisch aus dem Standby (falls nötig), wählt das Espresso-Programm aus und startet es.

### Standard-Espresso (50 ml)

```bash
make brew
```

### Individuelle Füllmenge

Die Füllmenge kann zwischen 35-50 ml gewählt werden:

```bash
make brew FILL_ML=40
```

oder

```bash
make brew FILL_ML=50
```

### Mit Status-Überwachung

Um den Status während der Zubereitung zu überwachen:

```bash
make brew BREW_ARGS="--poll"
```

### Kombinierte Optionen

```bash
# 45 ml mit Status-Überwachung
make brew FILL_ML=45 BREW_ARGS="--poll"
```

### Direktes Python-Skript

Alternativ kannst du das Skript auch direkt aufrufen:

```bash
python -m scripts.brew_espresso --fill-ml 50 --poll
```

**Hinweis:** Das Skript aktiviert das Gerät automatisch aus dem Standby, falls nötig. Die Füllmenge muss zwischen 35-50 ml liegen (gerätespezifische Einschränkung).

## Verfügbare Makefile-Kommandos

| Kommando | Beschreibung |
|----------|--------------|
| `make init` | Richtet die virtuelle Umgebung ein und installiert Dependencies |
| `make auth` | Startet den OAuth-Flow zur Authentifizierung |
| `make wake` | Aktiviert das Gerät aus dem Standby-Modus |
| `make status` | Zeigt alle registrierten Geräte und den aktuellen Status |
| `make brew` | Startet einen Espresso (aktiviert Gerät automatisch) |
| `make events` | Überwacht den Event-Stream in Echtzeit |
| `make server` | Startet HTTP-Server für Siri Shortcuts Integration |
| `make cert` | Erstellt selbstsigniertes SSL-Zertifikat |
| `make cert_install` | Installiert Zertifikat im Mac Schlüsselbund |
| `make cert_export` | Öffnet Finder mit Zertifikat für AirDrop-Transfer |
| `make clean_tokens` | Löscht die gespeicherten Tokens |

### Beispiele

```bash
# Gerät aktivieren
make wake

# Status abrufen
make status

# Espresso mit Standard-Einstellungen (50 ml)
make brew

# Espresso mit individueller Menge
make brew FILL_ML=40

# Espresso mit Status-Überwachung
make brew BREW_ARGS="--poll"

# Events überwachen (bricht nach 10 Events ab)
make events EVENTS_LIMIT=10
```

## Siri Shortcuts Integration

Du kannst die Kaffeemaschine auch per Siri Shortcut steuern! Dafür stehen Shell-Scripts zur Verfügung:

### Gerät aktivieren

1. Öffne die **Shortcuts App** auf deinem iPhone/iPad/Mac
2. Erstelle einen neuen Shortcut
3. Füge eine **"Shell-Script ausführen"** Aktion hinzu
4. Wähle als Script:
   ```bash
   /Users/tim/Development/HomeConnectCoffee/scripts/wake.sh
   ```
5. Benenne den Shortcut z.B. "Kaffeemaschine aktivieren"
6. Aktiviere **"Mit Siri verwenden"** und wähle einen Spruch wie "Kaffeemaschine aktivieren"

### Espresso starten

1. Erstelle einen neuen Shortcut
2. Füge eine **"Shell-Script ausführen"** Aktion hinzu
3. Wähle als Script:
   ```bash
   /Users/tim/Development/HomeConnectCoffee/scripts/brew.sh
   ```
   Oder mit individueller Menge:
   ```bash
   /Users/tim/Development/HomeConnectCoffee/scripts/brew.sh 40
   ```
4. Benenne den Shortcut z.B. "Espresso machen"
5. Aktiviere **"Mit Siri verwenden"** und wähle einen Spruch wie "Mach mir einen Espresso"

**Hinweis:** Die Shell-Scripts funktionieren am besten auf macOS. Für iOS/iPadOS siehe HTTP-Server Option unten.

### HTTP-Server für iOS/iPadOS (empfohlen)

Für iOS/iPadOS ist ein HTTP-Server die bessere Lösung:

1. **Starte den Server auf deinem Mac:**
   ```bash
   make server
   ```
   Der Server läuft standardmäßig auf `http://localhost:8080`

2. **Für Zugriff von iOS/iPadOS:** Starte den Server mit deiner Mac-IP-Adresse:
   ```bash
   make server SERVER_ARGS="--host 0.0.0.0 --port 8080"
   ```
   Finde deine Mac-IP-Adresse mit: `ifconfig | grep "inet "`

3. **Mit Authentifizierung und TLS:**
   ```bash
   make server SERVER_ARGS="--host 0.0.0.0 --port 8080 --api-token mein-token --cert certs/server.crt --key certs/server.key"
   ```

4. **Logging deaktivieren:** Wenn du keine Request-Logs sehen möchtest:
   ```bash
   make server SERVER_ARGS="--no-log"
   ```
   Standardmäßig ist Logging aktiviert und zeigt alle Requests mit Zeitstempel, IP-Adresse, Methode, Pfad und Status-Code. **Token werden im Log automatisch maskiert** (als `***` angezeigt).

### SSL/TLS Zertifikat erstellen

Für HTTPS benötigst du ein SSL-Zertifikat:

```bash
# Zertifikat erstellen
make cert

# Zertifikat im Mac Schlüsselbund installieren (für vertrauenswürdige Verbindungen)
make cert_install
```

Das Zertifikat wird im `certs/` Verzeichnis erstellt und ist für `localhost` und `*.local` Domains gültig.

### Zertifikat auf iOS installieren

Für die Verwendung mit Apple Shortcuts auf iOS/iPadOS musst du das Zertifikat auf deinem Gerät installieren. Es gibt zwei Methoden:

#### Methode 1: AirDrop (empfohlen)

1. **Zertifikat für AirDrop vorbereiten:**
   ```bash
   make cert_export
   ```
   Dies öffnet den Finder mit dem Zertifikat.

2. **Per AirDrop senden:**
   - Wähle die Datei `server.crt` im Finder aus
   - Rechtsklick → Teilen → AirDrop
   - Wähle dein iOS-Gerät aus

3. **Auf iOS installieren:**
   - Öffne die Datei auf dem iOS-Gerät
   - Tippe auf "Installieren"
   - Gehe zu **Einstellungen → Allgemein → VPN & Geräteverwaltung**
   - Tippe auf "HomeConnect Coffee" (unter "Zertifikat")
   - Tippe auf "Installieren" und bestätige

#### Methode 2: Download über Browser

1. **Server starten** (falls noch nicht gestartet):
   ```bash
   make server SERVER_ARGS="--host 0.0.0.0 --port 8080 --cert certs/server.crt --key certs/server.key"
   ```

2. **Zertifikat auf iOS herunterladen:**
   - Öffne Safari auf deinem iOS-Gerät
   - Navigiere zu: `https://DEINE_MAC_IP:8080/cert` (z.B. `https://elias.local:8080/cert`)
   - **Wichtig:** Bei der Warnung "Ungültiges Zertifikat" tippe auf "Erweitert" → "Trotzdem fortfahren"
   - Das Zertifikat wird heruntergeladen

3. **Zertifikat installieren:**
   - Öffne die heruntergeladene Datei
   - Tippe auf "Installieren"
   - Gehe zu **Einstellungen → Allgemein → VPN & Geräteverwaltung**
   - Tippe auf "HomeConnect Coffee" (unter "Zertifikat")
   - Tippe auf "Installieren" und bestätige

**Hinweis:** Nach der Installation musst du das Zertifikat als vertrauenswürdig markieren:
- **Einstellungen → Allgemein → Über → Zertifikatvertrauenseinstellungen**
- Aktiviere "HomeConnect Coffee" unter "Root-Zertifikate"

### Authentifizierung

Der Server unterstützt Token-basierte Authentifizierung:

**Option 1: Bearer Token im Header**
```bash
curl -H "Authorization: Bearer mein-token" https://elias.local:8080/wake
```

**Option 2: Token als URL-Parameter**
```bash
curl https://elias.local:8080/wake?token=mein-token
```

**Hinweis:** Token in URL-Parametern werden im Log automatisch als `***` maskiert.

**Token setzen:**
- Als Kommandozeilen-Argument: `--api-token mein-token`
- Oder als Umgebungsvariable: `COFFEE_API_TOKEN=mein-token`

3. **Erstelle Shortcuts in der Shortcuts App:**

   **Wake (Gerät aktivieren) - mit Token:**
   - Füge eine **"URL abrufen"** Aktion hinzu
   - URL: `https://DEINE_MAC_IP:8080/wake?token=DEIN_TOKEN`
   - Oder mit Header: Füge **"Header anfordern"** hinzu mit `Authorization: Bearer DEIN_TOKEN`
   - Aktiviere **"Mit Siri verwenden"**

   **Brew (Espresso starten) - mit Token:**
   - Füge eine **"URL abrufen"** Aktion hinzu
   - Methode: **POST**
   - URL: `https://DEINE_MAC_IP:8080/brew?token=DEIN_TOKEN`
   - Request Body: JSON
   - Body-Inhalt: `{"fill_ml": 50}`
   - Oder mit Header: Füge **"Header anfordern"** hinzu mit `Authorization: Bearer DEIN_TOKEN`
   - Aktiviere **"Mit Siri verwenden"`

   **Hinweis:** Bei HTTPS mit selbstsigniertem Zertifikat musst du das Zertifikat zuerst im iOS-Gerät installieren oder die Zertifikatsprüfung in den Shortcuts deaktivieren.

**Verfügbare Endpoints:**
- `GET /cert` - Download SSL-Zertifikat (öffentlich, keine Authentifizierung)
- `GET /wake` - Aktiviert das Gerät
- `GET /status` - Zeigt den Gerätestatus
- `POST /brew` - Startet einen Espresso (JSON: `{"fill_ml": 50}`)
- `GET /health` - Health-Check

## Weitere Ideen

- `scripts/device_status.py` zeigt alle verfügbaren Programme/Optionen
- `scripts/events.py` öffnet den SSE-Eventstream (Monitoring)
- Integration in Home Assistant oder Shortcut möglich, solange Token gültig sind.

## Sicherheit

HomeConnect lässt aktuell keinen direkten Offline-Zugriff im Heimnetz zu. Alle Befehle laufen über die Bosch-Cloud. Schütze deine Client-Secret-Dateien und Tokens entsprechend.

## Ressourcen

- [API-Dokumentation](https://developer.home-connect.com/docs)
- [Programmliste Kaffeemaschine](https://developer.home-connect.com/docs/programs_and_options)
- [Beispiel Postman Collection](https://developer.home-connect.com/docs/postman)
