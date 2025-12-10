"""Unit tests for client.py (HomeConnectClient)."""

from __future__ import annotations

from datetime import timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from homeconnect_coffee.client import HomeConnectClient


@pytest.mark.unit
class TestHomeConnectClient:
    """Tests for HomeConnectClient class."""

    def test_init_without_token_raises_error(self, test_config):
        """Test that __init__ raises an error when no token is found."""
        # Token file does not exist
        with pytest.raises(RuntimeError, match="No token found"):
            HomeConnectClient(test_config)

    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.record_token_refresh")
    @patch("homeconnect_coffee.client.requests.Session")
    def test_get_status(self, mock_session_class, mock_record_token_refresh, mock_record_api_call, test_config, valid_token_bundle, temp_token_file):
        """Test get_status() makes correct API call."""
        # Save token
        valid_token_bundle.save(temp_token_file)
        
        # Mock Session and its request method
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock API response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"status": []}}
        mock_session.request.return_value = mock_response
        
        client = HomeConnectClient(test_config)
        result = client.get_status()
        
        # Check that API call was made
        mock_session.request.assert_called_once()
        call_args = mock_session.request.call_args
        assert call_args[0][0] == "GET"
        assert "/homeappliances/test_haid/status" in call_args[0][1]
        
        # Check that monitoring was called
        mock_record_api_call.assert_called_once()
        
        # Check that correct headers were sent
        headers = call_args[1]["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_access_token"
        
        assert result == {"data": {"status": []}}

    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.record_token_refresh")
    @patch("homeconnect_coffee.client.requests.Session")
    def test_get_status_with_custom_haid(self, mock_session_class, mock_record_token_refresh, mock_record_api_call, test_config, valid_token_bundle, temp_token_file):
        """Test get_status() with custom haid."""
        valid_token_bundle.save(temp_token_file)
        
        # Mock Session and its request method
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"status": []}}
        mock_session.request.return_value = mock_response
        
        client = HomeConnectClient(test_config)
        client.get_status(haid="custom_haid")
        
        call_args = mock_session.request.call_args
        assert "/homeappliances/custom_haid/status" in call_args[0][1]

    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.record_token_refresh")
    @patch("homeconnect_coffee.client.requests.Session")
    def test_select_program(self, mock_session_class, mock_record_token_refresh, mock_record_api_call, test_config, valid_token_bundle, temp_token_file):
        """Test select_program() makes correct API call."""
        valid_token_bundle.save(temp_token_file)
        
        # Mock Session and its request method
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"key": "Espresso"}}
        mock_session.request.return_value = mock_response
        
        client = HomeConnectClient(test_config)
        options = [{"key": "FillQuantity", "value": 50}]
        result = client.select_program("Espresso", options=options)
        
        call_args = mock_session.request.call_args
        assert call_args[0][0] == "PUT"
        assert "/homeappliances/test_haid/programs/selected" in call_args[0][1]
        
        # Check payload
        json_payload = call_args[1]["json"]
        assert json_payload["data"]["key"] == "Espresso"
        assert json_payload["data"]["options"] == options

    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.record_token_refresh")
    @patch("homeconnect_coffee.client.requests.Session")
    def test_start_program(self, mock_session_class, mock_record_token_refresh, mock_record_api_call, test_config, valid_token_bundle, temp_token_file):
        """Test start_program() makes correct API calls."""
        valid_token_bundle.save(temp_token_file)
        
        # Mock Session and its request method
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock for get_selected_program
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
        
        # Mock for start_program
        start_response = Mock()
        start_response.ok = True
        start_response.status_code = 200
        start_response.json.return_value = {"data": {"key": "Espresso"}}
        
        # Mock request() to return different responses
        def request_side_effect(*args, **kwargs):
            if "selected" in args[1]:
                return selected_response
            elif "active" in args[1]:
                return start_response
            return start_response
        
        mock_session.request.side_effect = request_side_effect
        
        client = HomeConnectClient(test_config)
        result = client.start_program()
        
        # Check that 2 API calls were made (selected + active)
        assert mock_session.request.call_count == 2
        
        # Check that AromaSelect was filtered
        active_call = [call for call in mock_session.request.call_args_list if "active" in call[0][1]][0]
        json_payload = active_call[1]["json"]
        options = json_payload["data"]["options"]
        assert len(options) == 1  # AromaSelect should be removed
        assert options[0]["key"] == "FillQuantity"

    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.record_token_refresh")
    @patch("homeconnect_coffee.client.requests.Session")
    def test_api_error_raises_runtime_error(self, mock_session_class, mock_record_token_refresh, mock_record_api_call, test_config, valid_token_bundle, temp_token_file):
        """Test that API errors raise RuntimeError."""
        valid_token_bundle.save(temp_token_file)
        
        # Mock Session and its request method
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.json.return_value = {"error": "Not Found"}
        mock_session.request.return_value = mock_response
        
        client = HomeConnectClient(test_config)
        
        with pytest.raises(RuntimeError, match="API request failed"):
            client.get_status()

    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.record_token_refresh")
    @patch("homeconnect_coffee.client.requests.Session")
    def test_204_response_returns_empty_dict(self, mock_session_class, mock_record_token_refresh, mock_record_api_call, test_config, valid_token_bundle, temp_token_file):
        """Test that 204 response returns empty dict."""
        valid_token_bundle.save(temp_token_file)
        
        # Mock Session and its request method
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 204
        mock_session.request.return_value = mock_response
        
        client = HomeConnectClient(test_config)
        result = client.stop_program()
        
        assert result == {}

    @patch("homeconnect_coffee.client.refresh_access_token")
    @patch("homeconnect_coffee.client.record_api_call")
    @patch("homeconnect_coffee.client.record_token_refresh")
    @patch("homeconnect_coffee.client.requests.Session")
    def test_token_refresh_on_expired_token(
        self, 
        mock_session_class,
        mock_record_token_refresh,
        mock_record_api_call, 
        mock_refresh,
        test_config, 
        expired_token_bundle, 
        temp_token_file
    ):
        """Test that expired tokens are automatically renewed."""
        expired_token_bundle.save(temp_token_file)
        
        # Mock Session and its request method
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock for token refresh
        from datetime import datetime
        new_token = expired_token_bundle.__class__(
            access_token="new_access_token",
            refresh_token="test_refresh_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope="test_scope",
            token_type="Bearer",
        )
        mock_refresh.return_value = new_token
        
        # Mock for API response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"status": []}}
        mock_session.request.return_value = mock_response
        
        client = HomeConnectClient(test_config)
        client.get_status()
        
        # Check that token refresh was called
        mock_refresh.assert_called_once_with(test_config, "test_refresh_token")
        
        # Check that token refresh was recorded
        mock_record_token_refresh.assert_called_once()
        
        # Check that new token was used
        call_args = mock_session.request.call_args
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer new_access_token"

    def test_get_access_token(self, test_config, valid_token_bundle, temp_token_file):
        """Test get_access_token() returns token."""
        valid_token_bundle.save(temp_token_file)
        
        client = HomeConnectClient(test_config)
        token = client.get_access_token()
        
        assert token == "test_access_token"

