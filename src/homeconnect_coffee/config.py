from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class HomeConnectConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    haid: str
    scope: str
    token_path: Path


REQUIRED_VARS = {
    "HOME_CONNECT_CLIENT_ID": "client_id",
    "HOME_CONNECT_CLIENT_SECRET": "client_secret",
    "HOME_CONNECT_REDIRECT_URI": "redirect_uri",
    "HOME_CONNECT_HAID": "haid",
}


def load_config() -> HomeConnectConfig:
    missing: list[str] = [var for var in REQUIRED_VARS if not os.getenv(var)]
    if missing:
        missing_fmt = ", ".join(missing)
        raise RuntimeError(f"Fehlende Umgebungsvariablen: {missing_fmt}")

    scope = os.getenv(
        "HOME_CONNECT_SCOPE",
        "IdentifyAppliance Control CoffeeMaker Settings Monitor",
    )
    token_path = Path(os.getenv("HOME_CONNECT_TOKEN_PATH", "tokens.json")).expanduser()

    return HomeConnectConfig(
        client_id=os.environ["HOME_CONNECT_CLIENT_ID"],
        client_secret=os.environ["HOME_CONNECT_CLIENT_SECRET"],
        redirect_uri=os.environ["HOME_CONNECT_REDIRECT_URI"],
        haid=os.environ["HOME_CONNECT_HAID"],
        scope=scope,
        token_path=token_path,
    )
