"""Tests für ErrorHandler mit RuntimeError 429."""

from __future__ import annotations

import pytest

from homeconnect_coffee.errors import ErrorCode, ErrorHandler


@pytest.mark.unit
class TestErrorHandlerRuntime429:
    """Tests für ErrorHandler mit RuntimeError bei 429."""

    def test_handle_error_runtime_error_429(self):
        """Test dass RuntimeError mit (429) als Rate-Limit erkannt wird."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = RuntimeError("API-Anfrage fehlgeschlagen (429): Rate limit exceeded")
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.GATEWAY_TIMEOUT
        assert response["error"] == "Rate-Limit erreicht. Bitte später erneut versuchen."
        assert response["code"] == ErrorCode.GATEWAY_TIMEOUT
        assert response["error_code"] == ErrorCode.API_ERROR

    def test_handle_error_runtime_error_429_different_message(self):
        """Test dass RuntimeError mit (429) in verschiedenen Nachrichten erkannt wird."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = RuntimeError("API-Anfrage fehlgeschlagen (429): Too Many Requests")
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.GATEWAY_TIMEOUT
        assert "Rate-Limit" in response["error"]

    def test_handle_error_runtime_error_not_429(self):
        """Test dass RuntimeError ohne (429) nicht als Rate-Limit behandelt wird."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = RuntimeError("API-Anfrage fehlgeschlagen (500): Internal Server Error")
        code, response = handler.handle_error(
            exception,
            default_code=ErrorCode.INTERNAL_SERVER_ERROR,
            default_message="Ein Fehler ist aufgetreten",
        )
        
        assert code == ErrorCode.INTERNAL_SERVER_ERROR
        assert response["error"] == "Ein Fehler ist aufgetreten"
        assert response["code"] == ErrorCode.INTERNAL_SERVER_ERROR

    def test_handle_error_runtime_error_generic(self):
        """Test dass generischer RuntimeError normal behandelt wird."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = RuntimeError("Unerwarteter Fehler")
        code, response = handler.handle_error(
            exception,
            default_code=ErrorCode.INTERNAL_SERVER_ERROR,
            default_message="Ein Fehler ist aufgetreten",
        )
        
        assert code == ErrorCode.INTERNAL_SERVER_ERROR
        assert response["error"] == "Ein Fehler ist aufgetreten"

