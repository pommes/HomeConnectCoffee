from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode
import json

import requests

from .config import HomeConnectConfig

AUTH_BASE = "https://api.home-connect.com/security/oauth"
TOKEN_ENDPOINT = f"{AUTH_BASE}/token"
AUTHORIZE_ENDPOINT = f"{AUTH_BASE}/authorize"


@dataclass
class TokenBundle:
    access_token: str
    refresh_token: str
    expires_at: datetime
    scope: str
    token_type: str

    @classmethod
    def from_response(cls, payload: dict[str, Any]) -> "TokenBundle":
        expires_in = int(payload.get("expires_in", 0)) or 0
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        return cls(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token", ""),
            expires_at=expires_at,
            scope=payload.get("scope", ""),
            token_type=payload.get("token_type", "Bearer"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat(),
            "scope": self.scope,
            "token_type": self.token_type,
        }

    @classmethod
    def from_file(cls, path: Path) -> Optional["TokenBundle"]:
        if not path.exists():
            return None
        payload = json.loads(path.read_text())
        expires_at = datetime.fromisoformat(payload["expires_at"])
        return cls(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token", ""),
            expires_at=expires_at,
            scope=payload.get("scope", ""),
            token_type=payload.get("token_type", "Bearer"),
        )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


def build_authorize_url(config: HomeConnectConfig, state: str | None = None) -> str:
    params = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": config.scope,
    }
    if state:
        params["state"] = state
    return f"{AUTHORIZE_ENDPOINT}?{urlencode(params)}"


def _token_request(config: HomeConnectConfig, data: Dict[str, str]) -> TokenBundle:
    auth = (config.client_id, config.client_secret)
    response = requests.post(TOKEN_ENDPOINT, data=data, auth=auth, timeout=30)
    response.raise_for_status()
    return TokenBundle.from_response(response.json())


def exchange_code_for_tokens(config: HomeConnectConfig, code: str) -> TokenBundle:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.redirect_uri,
    }
    return _token_request(config, data)


def refresh_access_token(config: HomeConnectConfig, refresh_token: str) -> TokenBundle:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    return _token_request(config, data)
