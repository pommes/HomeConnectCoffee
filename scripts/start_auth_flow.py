from __future__ import annotations

import argparse
import textwrap
import webbrowser

from rich import print

from homeconnect_coffee.auth import build_authorize_url, exchange_code_for_tokens
from homeconnect_coffee.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Starts the HomeConnect OAuth flow")
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Attempts to automatically open the authorize URL in the default browser.",
    )
    parser.add_argument(
        "--code",
        type=str,
        help="Authorization code passed directly as argument (optional).",
    )
    args = parser.parse_args()

    config = load_config()
    authorize_url = build_authorize_url(config)

    print("[bold green]1. Open the following URL and log in:[/bold green]")
    print(textwrap.fill(authorize_url, width=100))

    if args.open_browser:
        webbrowser.open(authorize_url)

    if args.code:
        code = args.code.strip()
    else:
        code = input("\nEnter authorization code: ").strip()
    
    if not code:
        raise SystemExit("No code provided.")

    tokens = exchange_code_for_tokens(config, code)
    tokens.save(config.token_path)
    print(f"\n[bold]Tokens saved to:[/bold] {config.token_path}")


if __name__ == "__main__":
    main()
