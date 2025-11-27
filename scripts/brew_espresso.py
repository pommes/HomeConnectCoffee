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
    if strength is not None:
        options.append({"key": STRONG_OPTION, "value": strength})
    return options


def main() -> None:
    parser = argparse.ArgumentParser(description="Startet einen Espresso über die HomeConnect API")
    parser.add_argument("--fill-ml", type=int, default=60, help="Füllmenge in ml")
    parser.add_argument(
        "--strength",
        choices=["Mild", "Normal", "Strong"],
        default="Normal",
        help="Bohnenmenge/Stärke laut HomeConnect Optionen",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Status nach dem Start abfragen",
    )
    args = parser.parse_args()

    config = load_config()
    client = HomeConnectClient(config)

    options = build_options(args.fill_ml, args.strength)
    print("[bold]Programm auswählen...[/bold]")
    _ = client.select_program(ESPRESSO_KEY, options=options)

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
