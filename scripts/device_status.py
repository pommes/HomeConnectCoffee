from __future__ import annotations

import json

from rich import print

from homeconnect_coffee.client import HomeConnectClient
from homeconnect_coffee.config import load_config


def main() -> None:
    config = load_config()
    client = HomeConnectClient(config)

    appliances = client.get_home_appliances()
    print("[bold]Registrierte Geräte:[/bold]")
    print(json.dumps(appliances, indent=2))

    if config.haid:
        status = client.get_status()
        print("\n[bold]Aktueller Status der Kaffeemaschine:[/bold]")
        print(json.dumps(status, indent=2))
    else:
        print("\n[bold yellow]Hinweis:[/bold yellow] Keine HAID in der .env Datei konfiguriert.")
        print("Trage die HAID aus der Geräteliste oben in deine .env Datei ein.")


if __name__ == "__main__":
    main()
