from __future__ import annotations

from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional

import requests

from .api_monitor import record_api_call, record_token_refresh
from .auth import TokenBundle, refresh_access_token
from .config import HomeConnectConfig

logger = logging.getLogger(__name__)

BASE_API = "https://api.home-connect.com/api"
JSON_HEADER = "application/vnd.bsh.sdk.v1+json"

# Global lock for token refresh (prevents concurrent refreshes)
_token_refresh_lock = Lock()


class HomeConnectClient:
    def __init__(self, config: HomeConnectConfig) -> None:
        self.config = config
        tokens = TokenBundle.from_file(config.token_path)
        if not tokens:
            raise RuntimeError("No token found. Please run the auth flow first.")
        self.tokens = tokens
        # Create a session for connection pooling
        self._session = requests.Session()
        # Track if we've already retried a request (to prevent infinite loops)
        self._retry_attempted = False

    def _ensure_token(self) -> None:
        """Ensures token is valid, refreshing if necessary.
        
        Token refresh strategy:
        - Only refreshes when token is expired (not proactively)
        - Uses thread-safe lock to prevent concurrent refreshes
        - Reloads token from file if another thread already refreshed it
        - Records refresh for monitoring and logs the operation
        """
        if not self.tokens.refresh_token:
            return
        
        # Check if token is expired
        is_expired = self.tokens.is_expired()
        if not is_expired:
            # Token is still valid, no refresh needed
            return
        
        # Calculate time until expiry for logging (will be negative if expired)
        now = datetime.now(timezone.utc)
        time_until_expiry = (self.tokens.expires_at - now).total_seconds()
        
        logger.info(f"Token expired or expiring soon (expires_at: {self.tokens.expires_at.isoformat()}, "
                   f"seconds until expiry: {int(time_until_expiry)}). Refreshing access token...")
        
        # Use lock to ensure only one thread refreshes the token
        with _token_refresh_lock:
            # Check again if token was already refreshed (by another thread)
            if not self.tokens.is_expired():
                # Token was already refreshed by another thread, reload
                logger.debug("Token was already refreshed by another thread, reloading from file")
                self.tokens = TokenBundle.from_file(self.config.token_path)
                if not self.tokens:
                    raise RuntimeError("Token could not be loaded.")
                return
            
            # Refresh the token
            try:
                logger.debug("Requesting new access token via refresh_token")
                self.tokens = refresh_access_token(self.config, self.tokens.refresh_token)
                self.tokens.save(self.config.token_path)
                # Record token refresh for monitoring
                record_token_refresh()
                logger.info(f"Token refreshed successfully, expires at {self.tokens.expires_at.isoformat()}")
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}")
                # If refresh fails, try to reload token (might have been refreshed by another thread)
                reloaded_tokens = TokenBundle.from_file(self.config.token_path)
                if reloaded_tokens and not reloaded_tokens.is_expired():
                    logger.info("Reloaded token from file after refresh failure (may have been refreshed by another thread)")
                    self.tokens = reloaded_tokens
                else:
                    raise RuntimeError(f"Failed to refresh token: {e}")

    def _headers(self) -> Dict[str, str]:
        self._ensure_token()
        return {
            "Authorization": f"Bearer {self.tokens.access_token}",
            "Accept": JSON_HEADER,
            "Content-Type": JSON_HEADER,
        }

    def _request(
        self, method: str, endpoint: str, *, json_payload: Optional[Dict[str, Any]] = None, retry_on_401: bool = True
    ) -> Dict[str, Any]:
        """Makes an API request with automatic retry on 401 errors.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/homeappliances/{haid}/status")
            json_payload: Optional JSON payload for POST/PUT requests
            retry_on_401: Whether to automatically retry on 401 errors (prevents infinite loops)
        
        Returns:
            Response JSON data
        
        Raises:
            requests.exceptions.ConnectionError: Device offline or connection error
            requests.exceptions.Timeout: Request timeout
            RuntimeError: API request failed
        """
        # Record API call for monitoring
        record_api_call(endpoint, method)
        
        url = f"{BASE_API}{endpoint}"
        headers = self._headers()
        
        # Timeout: 10 seconds for connection, 30 seconds total
        try:
            resp = self._session.request(method, url, headers=headers, json=json_payload, timeout=(10, 30))
        except requests.exceptions.ConnectionError as e:
            # Connection errors (device offline) should be re-raised as-is
            raise
        except requests.exceptions.Timeout as e:
            # Timeout errors (device offline) should be re-raised as-is
            raise
        except requests.exceptions.RequestException as e:
            # Other request exceptions (network issues) should be re-raised as-is
            raise
        
        # Handle 401 Unauthorized - token might have expired
        # Automatic retry logic: refresh token and retry request once
        # The _retry_attempted flag prevents infinite retry loops by ensuring
        # each request can only trigger one retry attempt
        if resp.status_code == 401 and retry_on_401 and not self._retry_attempted:
            logger.info(f"Received 401 Unauthorized for {method} {endpoint}, refreshing token and retrying request")
            # Try to refresh token and retry once
            try:
                self._retry_attempted = True
                # Force token refresh
                with _token_refresh_lock:
                    if self.tokens.refresh_token:
                        self.tokens = refresh_access_token(self.config, self.tokens.refresh_token)
                        self.tokens.save(self.config.token_path)
                        # Record token refresh for monitoring
                        record_token_refresh()
                
                # Retry request with new token (disable retry to prevent infinite loop)
                headers = self._headers()
                resp = self._session.request(method, url, headers=headers, json=json_payload, timeout=(10, 30))
                logger.debug("Request retry after token refresh successful")
                self._retry_attempted = False  # Reset for next request
            except Exception as e:
                logger.warning(f"Token refresh and retry failed: {e}")
                self._retry_attempted = False  # Reset on error
                # If refresh fails, continue with original error handling
                pass
        
        if not resp.ok:
            error_detail = resp.text
            try:
                error_json = resp.json()
                error_detail = error_json.get("error", error_json.get("description", error_detail))
            except Exception:
                pass
            # Don't treat 409 Conflict as device offline - it's a different error
            # Check if status code indicates device offline (500, 502, 503, 504)
            if resp.status_code in [500, 502, 503, 504]:
                # These might indicate device offline - check error message
                error_lower = error_detail.lower()
                if any(keyword in error_lower for keyword in [
                    "timeout", "connection", "unreachable", "offline", "network"
                ]):
                    # Likely device offline - raise as ConnectionError
                    raise requests.exceptions.ConnectionError(f"Device appears offline: {error_detail}")
            # For 409 and other errors, raise RuntimeError which will be handled by ErrorHandler
            raise RuntimeError(f"API request failed ({resp.status_code}): {error_detail}")
        
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # Re-raise HTTPError as-is so ErrorHandler can classify it
            raise
        
        if resp.status_code == 204:
            return {}
        return resp.json()
    
    def __del__(self) -> None:
        """Cleanup: close session when client is destroyed."""
        if hasattr(self, '_session'):
            self._session.close()

    def get_access_token(self) -> str:
        """Returns the current access token and updates it if needed."""
        self._ensure_token()
        return self.tokens.access_token

    def get_home_appliances(self) -> Dict[str, Any]:
        return self._request("GET", "/homeappliances")

    def get_status(self, haid: Optional[str] = None) -> Dict[str, Any]:
        haid = haid or self.config.haid
        return self._request("GET", f"/homeappliances/{haid}/status")

    def select_program(
        self,
        program_key: str,
        *,
        options: Optional[list[Dict[str, Any]]] = None,
        haid: Optional[str] = None,
    ) -> Dict[str, Any]:
        haid = haid or self.config.haid
        payload = {
            "data": {
                "key": program_key,
                "options": options or [],
            }
        }
        return self._request("PUT", f"/homeappliances/{haid}/programs/selected", json_payload=payload)

    def start_program(self, haid: Optional[str] = None) -> Dict[str, Any]:
        haid = haid or self.config.haid
        # Get the selected program and use it as payload
        # The API expects the data object of the selected program
        selected = self._request("GET", f"/homeappliances/{haid}/programs/selected")
        program_data = selected.get("data", {})
        
        # Filter options that may not be supported
        # (e.g., AromaSelect is not supported by some devices)
        options = program_data.get("options", [])
        # Remove AromaSelect as it's often not supported
        filtered_options = [
            opt for opt in options
            if opt.get("key") != "ConsumerProducts.CoffeeMaker.Option.AromaSelect"
        ]
        
        payload = {
            "data": {
                "key": program_data.get("key"),
                "options": filtered_options,
            }
        }
        return self._request("PUT", f"/homeappliances/{haid}/programs/active", json_payload=payload)

    def stop_program(self, haid: Optional[str] = None) -> Dict[str, Any]:
        haid = haid or self.config.haid
        return self._request("DELETE", f"/homeappliances/{haid}/programs/active")

    def clear_selected_program(self, haid: Optional[str] = None) -> Dict[str, Any]:
        """Clears the currently selected program."""
        haid = haid or self.config.haid
        return self._request("DELETE", f"/homeappliances/{haid}/programs/selected")

    def get_settings(self, haid: Optional[str] = None) -> Dict[str, Any]:
        """Gets the device settings."""
        haid = haid or self.config.haid
        return self._request("GET", f"/homeappliances/{haid}/settings")

    def set_setting(self, key: str, value: Any, haid: Optional[str] = None) -> Dict[str, Any]:
        """Sets a device setting."""
        haid = haid or self.config.haid
        payload = {"data": {"key": key, "value": value}}
        return self._request("PUT", f"/homeappliances/{haid}/settings/{key}", json_payload=payload)

    def get_commands(self, haid: Optional[str] = None) -> Dict[str, Any]:
        """Gets the available device commands."""
        haid = haid or self.config.haid
        return self._request("GET", f"/homeappliances/{haid}/commands")

    def execute_command(self, command_key: str, *, data: Optional[Dict[str, Any]] = None, haid: Optional[str] = None) -> Dict[str, Any]:
        """Executes a command on the device."""
        haid = haid or self.config.haid
        payload = {"data": data or {}}
        return self._request("POST", f"/homeappliances/{haid}/commands/{command_key}", json_payload=payload)

    def get_programs(self, haid: Optional[str] = None) -> Dict[str, Any]:
        """Gets the available device programs."""
        haid = haid or self.config.haid
        return self._request("GET", f"/homeappliances/{haid}/programs/available")

    def get_selected_program(self, haid: Optional[str] = None) -> Dict[str, Any]:
        """Gets the currently selected program."""
        haid = haid or self.config.haid
        return self._request("GET", f"/homeappliances/{haid}/programs/selected")

    def get_active_program(self, haid: Optional[str] = None) -> Dict[str, Any]:
        """Gets the currently active (running) program."""
        haid = haid or self.config.haid
        return self._request("GET", f"/homeappliances/{haid}/programs/active")
