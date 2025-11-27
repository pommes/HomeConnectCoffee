from __future__ import annotations

import argparse
import json
from time import sleep

from rich import print

from homeconnect_coffee.client import HomeConnectClient
from homeconnect_coffee.config import load_config

ESPRESSO_KEY = "ConsumerProducts.CoffeeMaker.Program.Beverage.Espresso"
STRONG_OPTION = "ConsumerProducts.CoffeeMaker.Option.BeanAmount"
FILL_OPTION = "ConsumerProducts.CoffeeMaker.Option.FillQuantity"


def build_options(fill_ml: int | None, strength: str | None) -> list[dict[str, object]]:
    options: list[dict[str, object]] = []
    if fill_ml is not None:
        options.append({"key": FILL_OPTION, "value": fill_ml})
    # BeanAmount wird weggelassen, da die Werte gerätespezifisch sind
    # und möglicherweise nicht "Mild", "Normal", "Strong" sind
    # if strength is not None:
    #     options.append({"key": STRONG_OPTION, "value": strength})
    return options


def main() -> None:
    parser = argparse.ArgumentParser(description="Startet einen Espresso über die HomeConnect API")
    parser.add_argument("--fill-ml", type=int, default=50, help="Füllmenge in ml (35-50 ml für Espresso)")
    parser.add_argument(
        "--strength",
        choices=["Mild", "Normal", "Strong"],
        default=None,
        help="Bohnenmenge/Stärke (aktuell deaktiviert - gerätespezifische Werte erforderlich)",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Status nach dem Start abfragen",
    )
    args = parser.parse_args()

    config = load_config()
    client = HomeConnectClient(config)

    # Prüfe PowerState und aktiviere Gerät falls nötig
    print("[bold]Prüfe Gerätestatus...[/bold]")
    try:
        settings = client.get_settings()
        power_state = None
        for setting in settings.get("data", {}).get("settings", []):
            if setting.get("key") == "BSH.Common.Setting.PowerState":
                power_state = setting.get("value")
                break
        
        if power_state == "BSH.Common.EnumType.PowerState.Standby":
            print("[yellow]Gerät ist im Standby, aktiviere...[/yellow]")
            client.set_setting("BSH.Common.Setting.PowerState", "BSH.Common.EnumType.PowerState.On")
            sleep(2)  # Kurz warten, bis das Gerät aktiviert ist
    except Exception as e:
        print(f"[yellow]Konnte PowerState nicht prüfen/setzen: {e}[/yellow]")
        # Weiter versuchen, vielleicht ist das Gerät schon aktiv

    options = build_options(args.fill_ml, args.strength)
    
    # Zuerst eventuell vorhandenes ausgewähltes Programm löschen
    try:
        client.clear_selected_program()
    except Exception:
        pass  # Ignoriere Fehler, falls kein Programm ausgewählt ist
    
    print("[bold]Programm auswählen...[/bold]")
    max_retries = 5
    for attempt in range(max_retries):
        try:
            _ = client.select_program(ESPRESSO_KEY, options=options)
            break
        except RuntimeError as e:
            if "WrongOperationState" in str(e) and attempt < max_retries - 1:
                print(f"[yellow]Gerät noch nicht bereit, warte 2 Sekunden... (Versuch {attempt + 1}/{max_retries})[/yellow]")
                sleep(2)
            else:
                raise

    print("[bold green]Espresso wird gestartet...[/bold green]")
    client.start_program()

    if args.poll:
        print("Statusabfrage... (bricht nach 30s ab)")
        for _ in range(6):
            status = client.get_status()
            print(json.dumps(status, indent=2))
            sleep(5)


if __name__ == "__main__":
    main()
