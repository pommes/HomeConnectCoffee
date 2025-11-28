"""Pytest-Konfiguration und Fixtures."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from homeconnect_coffee.auth import TokenBundle
from homeconnect_coffee.config import HomeConnectConfig


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Erstellt ein temporäres Verzeichnis für Tests."""
    return tmp_path


@pytest.fixture
def temp_token_file(temp_dir: Path) -> Path:
    """Erstellt eine temporäre Token-Datei."""
    return temp_dir / "tokens.json"


@pytest.fixture
def temp_history_db(temp_dir: Path) -> Path:
    """Erstellt einen temporären Pfad für History-DB."""
    return temp_dir / "history.db"


@pytest.fixture
def valid_token_bundle() -> TokenBundle:
    """Erstellt ein gültiges TokenBundle für Tests."""
    return TokenBundle(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        scope="test_scope",
        token_type="Bearer",
    )


@pytest.fixture
def expired_token_bundle() -> TokenBundle:
    """Erstellt ein abgelaufenes TokenBundle für Tests."""
    return TokenBundle(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        scope="test_scope",
        token_type="Bearer",
    )


@pytest.fixture
def test_config(temp_dir: Path, temp_token_file: Path) -> HomeConnectConfig:
    """Erstellt eine Test-Konfiguration."""
    return HomeConnectConfig(
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:3000/callback",
        haid="test_haid",
        scope="test_scope",
        token_path=temp_token_file,
    )

