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
    # BeanAmount is omitted because values are device-specific
    # and may not be "Mild", "Normal", "Strong"
    # if strength is not None:
    #     options.append({"key": STRONG_OPTION, "value": strength})
    return options


def main() -> None:
    parser = argparse.ArgumentParser(description="Starts an espresso via the HomeConnect API")
    parser.add_argument("--fill-ml", type=int, default=50, help="Fill amount in ml (35-50 ml for espresso)")
    parser.add_argument(
        "--strength",
        choices=["Mild", "Normal", "Strong"],
        default=None,
        help="Bean amount/strength (currently disabled - device-specific values required)",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Query status after start",
    )
    args = parser.parse_args()

    config = load_config()
    client = HomeConnectClient(config)

    # Check PowerState and activate device if necessary
    print("[bold]Checking device status...[/bold]")
    try:
        settings = client.get_settings()
        power_state = None
        for setting in settings.get("data", {}).get("settings", []):
            if setting.get("key") == "BSH.Common.Setting.PowerState":
                power_state = setting.get("value")
                break
        
        if power_state == "BSH.Common.EnumType.PowerState.Standby":
            print("[yellow]Device is in standby, activating...[/yellow]")
            client.set_setting("BSH.Common.Setting.PowerState", "BSH.Common.EnumType.PowerState.On")
            sleep(2)  # Wait briefly until device is activated
    except Exception as e:
        print(f"[yellow]Could not check/set PowerState: {e}[/yellow]")
        # Continue trying, device might already be active

    options = build_options(args.fill_ml, args.strength)
    
    # First clear any existing selected program
    try:
        client.clear_selected_program()
    except Exception:
        pass  # Ignore errors if no program is selected
    
    print("[bold]Selecting program...[/bold]")
    max_retries = 5
    for attempt in range(max_retries):
        try:
            _ = client.select_program(ESPRESSO_KEY, options=options)
            break
        except RuntimeError as e:
            if "WrongOperationState" in str(e) and attempt < max_retries - 1:
                print(f"[yellow]Device not ready yet, waiting 2 seconds... (Attempt {attempt + 1}/{max_retries})[/yellow]")
                sleep(2)
            else:
                raise

    print("[bold green]Starting espresso...[/bold green]")
    client.start_program()

    if args.poll:
        print("Querying status... (aborts after 30s)")
        for _ in range(6):
            status = client.get_status()
            print(json.dumps(status, indent=2))
            sleep(5)


if __name__ == "__main__":
    main()
