from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from .auth import TokenBundle, refresh_access_token
from .config import HomeConnectConfig

BASE_API = "https://api.home-connect.com/api"
JSON_HEADER = "application/vnd.bsh.sdk.v1+json"


class HomeConnectClient:
    def __init__(self, config: HomeConnectConfig) -> None:
        self.config = config
        tokens = TokenBundle.from_file(config.token_path)
        if not tokens:
            raise RuntimeError("Kein Token gefunden. Bitte erst den Auth-Flow ausführen.")
        self.tokens = tokens

    def _ensure_token(self) -> None:
        if not self.tokens.refresh_token:
            return
        # Refresh kurz vor Ablauf
        if self.tokens.is_expired():
            self.tokens = refresh_access_token(self.config, self.tokens.refresh_token)
            self.tokens.save(self.config.token_path)

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
        url = f"{BASE_API}{endpoint}"
        resp = requests.request(method, url, headers=self._headers(), json=json_payload, timeout=30)
        if not resp.ok:
            error_detail = resp.text
            try:
                error_json = resp.json()
                error_detail = error_json.get("error", error_json.get("description", error_detail))
            except Exception:
                pass
            raise RuntimeError(f"API-Anfrage fehlgeschlagen ({resp.status_code}): {error_detail}")
        resp.raise_for_status()
        if resp.status_code == 204:
            return {}
        return resp.json()

    def get_access_token(self) -> str:
        """Gibt den aktuellen Access Token zurück und aktualisiert ihn bei Bedarf."""
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
        # Hole das ausgewählte Programm und verwende es als Payload
        # Die API erwartet das data-Objekt des ausgewählten Programms
        selected = self._request("GET", f"/homeappliances/{haid}/programs/selected")
        program_data = selected.get("data", {})
        
        # Filtere Optionen, die möglicherweise nicht unterstützt werden
        # (z.B. AromaSelect wird von manchen Geräten nicht unterstützt)
        options = program_data.get("options", [])
        # Entferne AromaSelect, da es oft nicht unterstützt wird
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
        """Löscht das aktuell ausgewählte Programm."""
        haid = haid or self.config.haid
        return self._request("DELETE", f"/homeappliances/{haid}/programs/selected")

    def get_settings(self, haid: Optional[str] = None) -> Dict[str, Any]:
        """Ruft die Einstellungen des Geräts ab."""
        haid = haid or self.config.haid
        return self._request("GET", f"/homeappliances/{haid}/settings")

    def set_setting(self, key: str, value: Any, haid: Optional[str] = None) -> Dict[str, Any]:
        """Setzt eine Einstellung des Geräts."""
        haid = haid or self.config.haid
        payload = {"data": {"key": key, "value": value}}
        return self._request("PUT", f"/homeappliances/{haid}/settings/{key}", json_payload=payload)

    def get_commands(self, haid: Optional[str] = None) -> Dict[str, Any]:
        """Ruft die verfügbaren Commands des Geräts ab."""
        haid = haid or self.config.haid
        return self._request("GET", f"/homeappliances/{haid}/commands")

    def execute_command(self, command_key: str, *, data: Optional[Dict[str, Any]] = None, haid: Optional[str] = None) -> Dict[str, Any]:
        """Führt einen Command am Gerät aus."""
        haid = haid or self.config.haid
        payload = {"data": data or {}}
        return self._request("POST", f"/homeappliances/{haid}/commands/{command_key}", json_payload=payload)
