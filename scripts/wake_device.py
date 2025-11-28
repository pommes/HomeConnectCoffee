from __future__ import annotations

from time import sleep

from rich import print

from homeconnect_coffee.client import HomeConnectClient
from homeconnect_coffee.config import load_config


def main() -> None:
    config = load_config()
    client = HomeConnectClient(config)

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
            sleep(2)  # Wait briefly for device to activate
            print("[bold green]Device activated![/bold green]")
        elif power_state == "BSH.Common.EnumType.PowerState.On":
            print("[green]Device is already activated.[/green]")
        else:
            print(f"[yellow]Unknown PowerState: {power_state}[/yellow]")
    except Exception as e:
        print(f"[red]Error activating device: {e}[/red]")
        raise


if __name__ == "__main__":
    main()

