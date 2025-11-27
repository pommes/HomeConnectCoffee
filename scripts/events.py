from __future__ import annotations

import argparse
import json

from rich import print
from sseclient import SSEClient

from homeconnect_coffee.client import HomeConnectClient
from homeconnect_coffee.config import load_config

EVENTS_URL = "https://api.home-connect.com/api/homeappliances/events"


def main() -> None:
    parser = argparse.ArgumentParser(description="Hört den HomeConnect Eventstream ab")
    parser.add_argument("--limit", type=int, default=0, help="Anzahl Events (0 = unendlich)")
    args = parser.parse_args()

    config = load_config()
    client = HomeConnectClient(config)
    token = client.get_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
    }

    print("[bold]Verbinde mit HomeConnect Events...[/bold]")

    count = 0
    try:
        for event in SSEClient(EVENTS_URL, headers=headers):
            if not event.data:
                continue
            print(f"\n[bold cyan]{event.event}[/bold cyan]")
            try:
                payload = json.loads(event.data)
                print(json.dumps(payload, indent=2))
            except json.JSONDecodeError:
                print(event.data)
            count += 1
            if args.limit and count >= args.limit:
                break
    except KeyboardInterrupt:
        print("\nAbgebrochen.")


if __name__ == "__main__":
    main()
