"""Unit tests for auth.py (TokenBundle)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from homeconnect_coffee.auth import TokenBundle


@pytest.mark.unit
class TestTokenBundle:
    """Tests for TokenBundle class."""

    def test_from_response(self):
        """Test TokenBundle.from_response() with valid data."""
        payload = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "scope": "test_scope",
            "token_type": "Bearer",
        }
        
        bundle = TokenBundle.from_response(payload)
        
        assert bundle.access_token == "test_access_token"
        assert bundle.refresh_token == "test_refresh_token"
        assert bundle.scope == "test_scope"
        assert bundle.token_type == "Bearer"
        assert bundle.expires_at > datetime.now(timezone.utc)
        assert bundle.expires_at <= datetime.now(timezone.utc) + timedelta(seconds=3600)

    def test_from_response_without_refresh_token(self):
        """Test TokenBundle.from_response() without refresh_token."""
        payload = {
            "access_token": "test_access_token",
            "expires_in": 3600,
            "scope": "test_scope",
            "token_type": "Bearer",
        }
        
        bundle = TokenBundle.from_response(payload)
        
        assert bundle.access_token == "test_access_token"
        assert bundle.refresh_token == ""

    def test_to_dict(self, valid_token_bundle: TokenBundle):
        """Test TokenBundle.to_dict()."""
        data = valid_token_bundle.to_dict()
        
        assert data["access_token"] == "test_access_token"
        assert data["refresh_token"] == "test_refresh_token"
        assert data["scope"] == "test_scope"
        assert data["token_type"] == "Bearer"
        assert "expires_at" in data
        assert isinstance(data["expires_at"], str)

    def test_save_and_from_file(self, valid_token_bundle: TokenBundle, temp_token_file: Path):
        """Test TokenBundle.save() and from_file()."""
        # Save TokenBundle
        valid_token_bundle.save(temp_token_file)
        
        # Load TokenBundle
        loaded = TokenBundle.from_file(temp_token_file)
        
        assert loaded is not None
        assert loaded.access_token == valid_token_bundle.access_token
        assert loaded.refresh_token == valid_token_bundle.refresh_token
        assert loaded.scope == valid_token_bundle.scope
        assert loaded.token_type == valid_token_bundle.token_type
        assert loaded.expires_at == valid_token_bundle.expires_at

    def test_from_file_nonexistent(self, temp_dir: Path):
        """Test TokenBundle.from_file() with non-existent file."""
        nonexistent = temp_dir / "nonexistent.json"
        result = TokenBundle.from_file(nonexistent)
        
        assert result is None

    def test_is_expired_valid(self, valid_token_bundle: TokenBundle):
        """Test is_expired() with valid token."""
        assert not valid_token_bundle.is_expired()

    def test_is_expired_expired(self, expired_token_bundle: TokenBundle):
        """Test is_expired() with expired token."""
        assert expired_token_bundle.is_expired()

    def test_from_file_invalid_json(self, temp_dir: Path):
        """Test TokenBundle.from_file() with invalid JSON."""
        invalid_file = temp_dir / "invalid.json"
        invalid_file.write_text("invalid json")
        
        # from_file should return None or raise an error
        # Currently it raises an error during JSON parsing
        with pytest.raises((json.JSONDecodeError, KeyError)):
            TokenBundle.from_file(invalid_file)

    def test_from_file_missing_fields(self, temp_dir: Path):
        """Test TokenBundle.from_file() with missing fields."""
        incomplete_file = temp_dir / "incomplete.json"
        incomplete_file.write_text('{"access_token": "test"}')
        
        # from_file should raise an error if expires_at is missing
        with pytest.raises(KeyError):
            TokenBundle.from_file(incomplete_file)

