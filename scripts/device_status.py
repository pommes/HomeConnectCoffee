from __future__ import annotations

import json

from rich import print

from homeconnect_coffee.client import HomeConnectClient
from homeconnect_coffee.config import load_config


def main() -> None:
    config = load_config()
    client = HomeConnectClient(config)

    appliances = client.get_home_appliances()
    print("[bold]Registered devices:[/bold]")
    print(json.dumps(appliances, indent=2))

    if config.haid:
        status = client.get_status()
        print("\n[bold]Current status of coffee machine:[/bold]")
        print(json.dumps(status, indent=2))
    else:
        print("\n[bold yellow]Note:[/bold yellow] No HAID configured in .env file.")
        print("Enter the HAID from the device list above into your .env file.")


if __name__ == "__main__":
    main()
