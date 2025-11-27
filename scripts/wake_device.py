from __future__ import annotations

from time import sleep

from rich import print

from homeconnect_coffee.client import HomeConnectClient
from homeconnect_coffee.config import load_config


def main() -> None:
    config = load_config()
    client = HomeConnectClient(config)

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
            print("[bold green]Gerät aktiviert![/bold green]")
        elif power_state == "BSH.Common.EnumType.PowerState.On":
            print("[green]Gerät ist bereits aktiviert.[/green]")
        else:
            print(f"[yellow]Unbekannter PowerState: {power_state}[/yellow]")
    except Exception as e:
        print(f"[red]Fehler beim Aktivieren: {e}[/red]")
        raise


if __name__ == "__main__":
    main()

