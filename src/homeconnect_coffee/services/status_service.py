"""Service for status queries."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict

from ..api_monitor import get_monitor
from ..auth import TokenBundle
from ..client import HomeConnectClient


class StatusService:
    """Service for status queries."""

    def __init__(self, client: HomeConnectClient) -> None:
        """Initializes the StatusService with a HomeConnectClient."""
        self.client = client
        # Cache for extended status to reduce API calls
        self._cache: Dict[str, Any] = {}
        self._cache_lock = threading.Lock()
        self._cache_ttl = 10  # Cache for 10 seconds

    def get_status(self) -> Dict[str, Any]:
        """Returns the device status.
        
        Returns:
            Dict with status data from the HomeConnect API
        """
        return self.client.get_status()

    def _get_token_status(self) -> Dict[str, Any]:
        """Returns token status information for debugging.
        
        Returns:
            Dict with token status:
            - valid: Whether token is valid (not expired)
            - expires_at: Token expiration timestamp (ISO format)
            - expires_in_seconds: Seconds until token expires (negative if expired)
            - has_refresh_token: Whether refresh token is available
        """
        try:
            tokens = TokenBundle.from_file(self.client.config.token_path)
            if not tokens:
                return {
                    "valid": False,
                    "error": "No token found",
                }
            
            now = datetime.now(timezone.utc)
            expires_in_seconds = (tokens.expires_at - now).total_seconds()
            
            return {
                "valid": not tokens.is_expired(),
                "expires_at": tokens.expires_at.isoformat(),
                "expires_in_seconds": int(expires_in_seconds),
                "has_refresh_token": bool(tokens.refresh_token),
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }

    def _fetch_extended_status(self) -> Dict[str, Any]:
        """Fetches extended status from API (internal method, not cached).
        
        Returns:
            Dict with extended status data
        """
        # Try to get status and settings - may fail if device is temporarily unavailable
        status = {}
        settings = {}
        
        try:
            status = self.client.get_status()
        except Exception:
            # Status unavailable - continue with other information
            pass
        
        try:
            settings = self.client.get_settings()
        except Exception:
            # Settings unavailable - continue with other information
            pass
        
        # Try to retrieve programs (may fail if device is not ready)
        programs_available = {}
        program_selected = {}
        program_active = {}
        
        try:
            programs_available = self.client.get_programs()
        except Exception:
            pass
        
        try:
            program_selected = self.client.get_selected_program()
        except Exception:
            pass
        
        try:
            program_active = self.client.get_active_program()
        except Exception:
            pass

        # Get token status for debugging
        token_status = self._get_token_status()

        # Get API statistics
        try:
            api_stats = get_monitor().get_stats()
        except Exception as e:
            # If monitoring fails, continue without stats
            logger.debug(f"Could not get API statistics: {e}")
            api_stats = {}

        return {
            "status": status,
            "settings": settings,
            "programs": {
                "available": programs_available,
                "selected": program_selected,
                "active": program_active,
            },
            "token": token_status,
            "api_stats": api_stats,
        }

    def get_extended_status(self) -> Dict[str, Any]:
        """Returns extended status with settings, programs, and token status.
        
        Uses caching to reduce API calls when multiple requests occur within
        the cache TTL (10 seconds).
        
        Returns:
            Dict with:
            - status: Device status (may be empty dict if unavailable)
            - settings: Device settings (may be empty dict if unavailable)
            - programs: {
                - available: Available programs
                - selected: Selected program
                - active: Active program
              }
            - token: Token status information (for debugging)
            - api_stats: API usage statistics
        """
        # Check cache first
        with self._cache_lock:
            if self._cache and (time.time() - self._cache.get('timestamp', 0)) < self._cache_ttl:
                # Cache hit - return cached data
                return self._cache['data']
        
        # Cache miss or expired - fetch new data
        data = self._fetch_extended_status()
        
        # Update cache
        with self._cache_lock:
            self._cache = {
                'data': data,
                'timestamp': time.time()
            }
        
        return data

