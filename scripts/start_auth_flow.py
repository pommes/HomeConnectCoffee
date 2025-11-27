from __future__ import annotations

import argparse
import textwrap
import webbrowser

from rich import print

from homeconnect_coffee.auth import build_authorize_url, exchange_code_for_tokens
from homeconnect_coffee.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Startet den HomeConnect OAuth Flow")
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Versucht, die Authorize-URL automatisch im Standardbrowser zu öffnen.",
    )
    args = parser.parse_args()

    config = load_config()
    authorize_url = build_authorize_url(config)

    print("[bold green]1. Öffne folgende URL und logge dich ein:[/bold green]")
    print(textwrap.fill(authorize_url, width=100))

    if args.open_browser:
        webbrowser.open(authorize_url)

    code = input("\nAuthorization Code eingeben: ").strip()
    if not code:
        raise SystemExit("Kein Code angegeben.")

    tokens = exchange_code_for_tokens(config, code)
    tokens.save(config.token_path)
    print(f"\n[bold]Tokens gespeichert unter:[/bold] {config.token_path}")


if __name__ == "__main__":
    main()
