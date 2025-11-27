# HomeConnect Coffee Steuerung

Dieses Projekt zeigt, wie du deine Bosch CTL7181B0 (und andere HomeConnect-Kaffeemaschinen) per Python-Skript über die offizielle HomeConnect-Cloud-API starten kannst.

## Voraussetzungen

1. **HomeConnect-Entwicklerkonto** auf [developer.home-connect.com](https://developer.home-connect.com)
2. **OAuth-Client** (Typ *Server Application*) mit Redirect-URL `http://localhost:3000/callback` oder ähnlich
3. **Gerät verknüpft** (über die HomeConnect-App)
4. Python 3.11+

## Einrichtung

```bash
cd /Users/tim/Development/HomeConnectCoffee
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Zugangsdaten eintragen
```

` .env` muss folgende Werte enthalten:

```
HOME_CONNECT_CLIENT_ID=
HOME_CONNECT_CLIENT_SECRET=
HOME_CONNECT_REDIRECT_URI=http://localhost:3000/callback
HOME_CONNECT_HAID=
HOME_CONNECT_SCOPE=IdentifyAppliance Control CoffeeMaker Settings Monitor
```

## Autorisierung anstoßen

```bash
python -m scripts.start_auth_flow
```

Der Befehl öffnet (bzw. zeigt) die Authorize-URL. Nach Login erhältst du einen `code`, den du ins Terminal kopierst. Das Skript speichert `tokens.json` mit Access- und Refresh-Token.

## Espresso starten

```bash
python -m scripts.brew_espresso --fill-ml 60
```

Das Skript:
- wählt das gewünschte Programm (`Beverage.Espresso`)
- setzt optional Menge, Stärke etc.
- startet das Programm und zeigt den Status.

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
