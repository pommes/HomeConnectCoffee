"""Unit-Tests für client.py (HomeConnectClient)."""

from __future__ import annotations

from datetime import timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from homeconnect_coffee.client import HomeConnectClient


@pytest.mark.unit
class TestHomeConnectClient:
    """Tests für HomeConnectClient Klasse."""

    def test_init_without_token_raises_error(self, test_config):
        """Test dass __init__ einen Fehler wirft, wenn kein Token gefunden wird."""
        # Token-Datei existiert nicht
        with pytest.raises(RuntimeError, match="Kein Token gefunden"):
            HomeConnectClient(test_config)

    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.requests.request")
    def test_get_status(self, mock_request, mock_record_api_call, test_config, valid_token_bundle, temp_token_file):
        """Test get_status() macht korrekten API-Call."""
        # Speichere Token
        valid_token_bundle.save(temp_token_file)
        
        # Mock API-Response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"status": []}}
        mock_request.return_value = mock_response
        
        client = HomeConnectClient(test_config)
        result = client.get_status()
        
        # Prüfe dass API-Call gemacht wurde
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/homeappliances/test_haid/status" in call_args[0][1]
        
        # Prüfe dass Monitoring aufgerufen wurde
        mock_record_api_call.assert_called_once()
        
        # Prüfe dass korrekte Headers gesendet wurden
        headers = call_args[1]["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_access_token"
        
        assert result == {"data": {"status": []}}

    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.requests.request")
    def test_get_status_with_custom_haid(self, mock_request, mock_record_api_call, test_config, valid_token_bundle, temp_token_file):
        """Test get_status() mit custom haid."""
        valid_token_bundle.save(temp_token_file)
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"status": []}}
        mock_request.return_value = mock_response
        
        client = HomeConnectClient(test_config)
        client.get_status(haid="custom_haid")
        
        call_args = mock_request.call_args
        assert "/homeappliances/custom_haid/status" in call_args[0][1]

    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.requests.request")
    def test_select_program(self, mock_request, mock_record_api_call, test_config, valid_token_bundle, temp_token_file):
        """Test select_program() macht korrekten API-Call."""
        valid_token_bundle.save(temp_token_file)
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"key": "Espresso"}}
        mock_request.return_value = mock_response
        
        client = HomeConnectClient(test_config)
        options = [{"key": "FillQuantity", "value": 50}]
        result = client.select_program("Espresso", options=options)
        
        call_args = mock_request.call_args
        assert call_args[0][0] == "PUT"
        assert "/homeappliances/test_haid/programs/selected" in call_args[0][1]
        
        # Prüfe Payload
        json_payload = call_args[1]["json"]
        assert json_payload["data"]["key"] == "Espresso"
        assert json_payload["data"]["options"] == options

    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.requests.request")
    def test_start_program(self, mock_request, mock_record_api_call, test_config, valid_token_bundle, temp_token_file):
        """Test start_program() macht korrekte API-Calls."""
        valid_token_bundle.save(temp_token_file)
        
        # Mock für get_selected_program
        selected_response = Mock()
        selected_response.ok = True
        selected_response.status_code = 200
        selected_response.json.return_value = {
            "data": {
                "key": "Espresso",
                "options": [
                    {"key": "FillQuantity", "value": 50},
                    {"key": "ConsumerProducts.CoffeeMaker.Option.AromaSelect", "value": "strong"}
                ]
            }
        }
        
        # Mock für start_program
        start_response = Mock()
        start_response.ok = True
        start_response.status_code = 200
        start_response.json.return_value = {"data": {"key": "Espresso"}}
        
        # Mock request() um verschiedene Responses zurückzugeben
        def request_side_effect(*args, **kwargs):
            if "selected" in args[1]:
                return selected_response
            elif "active" in args[1]:
                return start_response
            return start_response
        
        mock_request.side_effect = request_side_effect
        
        client = HomeConnectClient(test_config)
        result = client.start_program()
        
        # Prüfe dass 2 API-Calls gemacht wurden (selected + active)
        assert mock_request.call_count == 2
        
        # Prüfe dass AromaSelect gefiltert wurde
        active_call = [call for call in mock_request.call_args_list if "active" in call[0][1]][0]
        json_payload = active_call[1]["json"]
        options = json_payload["data"]["options"]
        assert len(options) == 1  # AromaSelect sollte entfernt sein
        assert options[0]["key"] == "FillQuantity"

    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.requests.request")
    def test_api_error_raises_runtime_error(self, mock_request, mock_record_api_call, test_config, valid_token_bundle, temp_token_file):
        """Test dass API-Fehler RuntimeError werfen."""
        valid_token_bundle.save(temp_token_file)
        
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.json.return_value = {"error": "Not Found"}
        mock_request.return_value = mock_response
        
        client = HomeConnectClient(test_config)
        
        with pytest.raises(RuntimeError, match="API-Anfrage fehlgeschlagen"):
            client.get_status()

    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.requests.request")
    def test_204_response_returns_empty_dict(self, mock_request, mock_record_api_call, test_config, valid_token_bundle, temp_token_file):
        """Test dass 204 Response leeres Dict zurückgibt."""
        valid_token_bundle.save(temp_token_file)
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 204
        mock_request.return_value = mock_response
        
        client = HomeConnectClient(test_config)
        result = client.stop_program()
        
        assert result == {}

    @patch("homeconnect_coffee.client.refresh_access_token")
    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.requests.request")
    def test_token_refresh_on_expired_token(
        self, 
        mock_request, 
        mock_record_api_call, 
        mock_refresh,
        test_config, 
        expired_token_bundle, 
        temp_token_file
    ):
        """Test dass abgelaufene Tokens automatisch erneuert werden."""
        expired_token_bundle.save(temp_token_file)
        
        # Mock für Token-Refresh
        from datetime import datetime
        new_token = expired_token_bundle.__class__(
            access_token="new_access_token",
            refresh_token="test_refresh_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope="test_scope",
            token_type="Bearer",
        )
        mock_refresh.return_value = new_token
        
        # Mock für API-Response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"status": []}}
        mock_request.return_value = mock_response
        
        client = HomeConnectClient(test_config)
        client.get_status()
        
        # Prüfe dass Token-Refresh aufgerufen wurde
        mock_refresh.assert_called_once_with(test_config, "test_refresh_token")
        
        # Prüfe dass neuer Token verwendet wurde
        call_args = mock_request.call_args
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer new_access_token"

    def test_get_access_token(self, test_config, valid_token_bundle, temp_token_file):
        """Test get_access_token() gibt Token zurück."""
        valid_token_bundle.save(temp_token_file)
        
        client = HomeConnectClient(test_config)
        token = client.get_access_token()
        
        assert token == "test_access_token"

