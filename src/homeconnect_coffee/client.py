from __future__ import annotations

from threading import Lock
from typing import Any, Dict, Optional

import requests

from .api_monitor import record_api_call
from .auth import TokenBundle, refresh_access_token
from .config import HomeConnectConfig

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

    def _ensure_token(self) -> None:
        if not self.tokens.refresh_token:
            return
        # Refresh shortly before expiration
        if self.tokens.is_expired():
            # Use lock to ensure only one thread refreshes the token
            with _token_refresh_lock:
                # Check again if token was already refreshed (by another thread)
                if self.tokens.is_expired():
                    self.tokens = refresh_access_token(self.config, self.tokens.refresh_token)
                    self.tokens.save(self.config.token_path)
                else:
                    # Token was already refreshed by another thread, reload
                    self.tokens = TokenBundle.from_file(self.config.token_path)
                    if not self.tokens:
                        raise RuntimeError("Token could not be loaded.")

    def _headers(self) -> Dict[str, str]:
        self._ensure_token()
        return {
            "Authorization": f"Bearer {self.tokens.access_token}",
            "Accept": JSON_HEADER,
            "Content-Type": JSON_HEADER,
        }

    def _request(
        self, method: str, endpoint: str, *, json_payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # Record API call for monitoring
        record_api_call(endpoint, method)
        
        url = f"{BASE_API}{endpoint}"
        # Timeout: 10 seconds for connection, 30 seconds total
        resp = requests.request(method, url, headers=self._headers(), json=json_payload, timeout=(10, 30))
        if not resp.ok:
            error_detail = resp.text
            try:
                error_json = resp.json()
                error_detail = error_json.get("error", error_json.get("description", error_detail))
            except Exception:
                pass
            raise RuntimeError(f"API request failed ({resp.status_code}): {error_detail}")
        resp.raise_for_status()
        if resp.status_code == 204:
            return {}
        return resp.json()

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
