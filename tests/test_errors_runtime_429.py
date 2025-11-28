"""Tests for ErrorHandler with RuntimeError 429."""

from __future__ import annotations

import pytest

from homeconnect_coffee.errors import ErrorCode, ErrorHandler


@pytest.mark.unit
class TestErrorHandlerRuntime429:
    """Tests for ErrorHandler with RuntimeError at 429."""

    def test_handle_error_runtime_error_429(self):
        """Test that RuntimeError with (429) is recognized as rate limit."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = RuntimeError("API request failed (429): Rate limit exceeded")
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.GATEWAY_TIMEOUT
        assert response["error"] == "Rate limit reached. Please try again later."
        assert response["code"] == ErrorCode.GATEWAY_TIMEOUT
        assert response["error_code"] == ErrorCode.API_ERROR

    def test_handle_error_runtime_error_429_different_message(self):
        """Test that RuntimeError with (429) is recognized in different messages."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = RuntimeError("API request failed (429): Too Many Requests")
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.GATEWAY_TIMEOUT
        assert "Rate limit" in response["error"]

    def test_handle_error_runtime_error_not_429(self):
        """Test that RuntimeError without (429) is not treated as rate limit."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = RuntimeError("API request failed (500): Internal Server Error")
        code, response = handler.handle_error(
            exception,
            default_code=ErrorCode.INTERNAL_SERVER_ERROR,
            default_message="Ein Fehler ist aufgetreten",
        )
        
        assert code == ErrorCode.INTERNAL_SERVER_ERROR
        assert response["error"] == "Ein Fehler ist aufgetreten"
        assert response["code"] == ErrorCode.INTERNAL_SERVER_ERROR

    def test_handle_error_runtime_error_generic(self):
        """Test that generic RuntimeError is handled normally."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = RuntimeError("Unexpected error")
        code, response = handler.handle_error(
            exception,
            default_code=ErrorCode.INTERNAL_SERVER_ERROR,
            default_message="Ein Fehler ist aufgetreten",
        )
        
        assert code == ErrorCode.INTERNAL_SERVER_ERROR
        assert response["error"] == "Ein Fehler ist aufgetreten"

