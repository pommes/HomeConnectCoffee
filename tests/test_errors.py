"""Unit tests for errors.py (ErrorHandler)."""

from __future__ import annotations

import logging
from unittest.mock import Mock, patch

import pytest
import requests

from homeconnect_coffee.errors import ErrorCode, ErrorHandler


@pytest.mark.unit
class TestErrorHandler:
    """Tests for ErrorHandler class."""

    def test_init(self):
        """Test that __init__ initializes the handler correctly."""
        handler = ErrorHandler(enable_logging=False)
        
        assert handler.enable_logging is False
        assert handler.log_sensitive is False

    def test_init_with_logging(self):
        """Test __init__ with logging enabled."""
        handler = ErrorHandler(enable_logging=True, log_sensitive=True)
        
        assert handler.enable_logging is True
        assert handler.log_sensitive is True

    def test_format_error_response(self):
        """Test format_error_response() creates correct format."""
        handler = ErrorHandler(enable_logging=False)
        
        response = handler.format_error_response(500, "Test-Fehler")
        
        assert response["error"] == "Test-Fehler"
        assert response["code"] == 500
        assert "error_code" not in response

    def test_format_error_response_with_error_code(self):
        """Test format_error_response() with error code."""
        handler = ErrorHandler(enable_logging=False)
        
        response = handler.format_error_response(
            500, "Test-Fehler", error_code=ErrorCode.INTERNAL_SERVER_ERROR
        )
        
        assert response["error"] == "Test-Fehler"
        assert response["code"] == 500
        assert response["error_code"] == ErrorCode.INTERNAL_SERVER_ERROR

    def test_format_error_response_with_details(self):
        """Test format_error_response() with details."""
        handler = ErrorHandler(enable_logging=False)
        
        response = handler.format_error_response(
            500, "Test-Fehler", details={"field": "value"}
        )
        
        assert response["error"] == "Test-Fehler"
        assert response["code"] == 500
        assert response["details"] == {"field": "value"}

    def test_handle_error_value_error(self):
        """Test handle_error() with ValueError."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = ValueError("Ungültiger Wert")
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.BAD_REQUEST
        assert response["error"] == "Invalid parameter: Ungültiger Wert"
        assert response["code"] == ErrorCode.BAD_REQUEST
        assert response["error_code"] == ErrorCode.VALIDATION_ERROR

    def test_handle_error_file_not_found(self):
        """Test handle_error() with FileNotFoundError."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = FileNotFoundError("Datei nicht gefunden")
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.NOT_FOUND
        assert response["error"] == "Datei nicht gefunden"
        assert response["code"] == ErrorCode.NOT_FOUND
        assert response["error_code"] == ErrorCode.FILE_ERROR

    def test_handle_error_timeout(self):
        """Test handle_error() with Timeout (device offline)."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = requests.exceptions.Timeout("Request timeout")
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.SERVICE_UNAVAILABLE
        assert response["error"] == "Device is offline or unreachable"
        assert response["code"] == ErrorCode.SERVICE_UNAVAILABLE
        assert response["error_code"] == ErrorCode.API_ERROR

    def test_handle_error_connection_error(self):
        """Test handle_error() with ConnectionError (device offline)."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = requests.exceptions.ConnectionError("Connection failed")
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.SERVICE_UNAVAILABLE
        assert response["error"] == "Device is offline or unreachable"
        assert response["code"] == ErrorCode.SERVICE_UNAVAILABLE
        assert response["error_code"] == ErrorCode.API_ERROR

    def test_handle_error_http_error_401(self):
        """Test handle_error() with HTTPError 401."""
        handler = ErrorHandler(enable_logging=False)
        
        response_mock = Mock()
        response_mock.status_code = 401
        
        exception = requests.exceptions.HTTPError("Unauthorized")
        exception.response = response_mock
        exception.__class__.__name__ = "HTTPError"
        
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.UNAUTHORIZED
        assert "Unauthorized" in response["error"]
        assert response["code"] == ErrorCode.UNAUTHORIZED
        assert response["error_code"] == ErrorCode.API_ERROR

    def test_handle_error_http_error_429(self):
        """Test handle_error() with HTTPError 429 (Rate Limit)."""
        handler = ErrorHandler(enable_logging=False)
        
        response_mock = Mock()
        response_mock.status_code = 429
        
        exception = requests.exceptions.HTTPError("Too Many Requests")
        exception.response = response_mock
        exception.__class__.__name__ = "HTTPError"
        
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.GATEWAY_TIMEOUT
        assert "Rate limit" in response["error"]
        assert response["code"] == ErrorCode.GATEWAY_TIMEOUT
        assert response["error_code"] == ErrorCode.API_ERROR

    def test_handle_error_generic_exception(self):
        """Test handle_error() with generic exception."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = RuntimeError("Unerwarteter Fehler")
        code, response = handler.handle_error(
            exception,
            default_code=ErrorCode.INTERNAL_SERVER_ERROR,
            default_message="Ein Fehler ist aufgetreten",
        )
        
        assert code == ErrorCode.INTERNAL_SERVER_ERROR
        assert response["error"] == "Ein Fehler ist aufgetreten"
        assert response["code"] == ErrorCode.INTERNAL_SERVER_ERROR
        assert response["error_code"] == ErrorCode.INTERNAL_SERVER_ERROR

    def test_handle_error_with_traceback(self):
        """Test handle_error() with traceback (only when log_sensitive=True)."""
        handler = ErrorHandler(enable_logging=False, log_sensitive=True)
        
        exception = RuntimeError("Test")
        code, response = handler.handle_error(
            exception,
            include_traceback=True,
        )
        
        # Traceback should be included when log_sensitive=True
        assert "traceback" in response

    def test_handle_error_without_traceback(self):
        """Test handle_error() without traceback (when log_sensitive=False)."""
        handler = ErrorHandler(enable_logging=False, log_sensitive=False)
        
        exception = RuntimeError("Test")
        code, response = handler.handle_error(
            exception,
            include_traceback=True,
        )
        
        # Traceback should NOT be included when log_sensitive=False
        assert "traceback" not in response

    def test_create_error_response(self):
        """Test create_error_response() for manual errors."""
        handler = ErrorHandler(enable_logging=False)
        
        response = handler.create_error_response(
            ErrorCode.NOT_FOUND,
            "Resource not found",
            ErrorCode.FILE_ERROR,
        )
        
        assert response["error"] == "Resource not found"
        assert response["code"] == ErrorCode.NOT_FOUND
        assert response["error_code"] == ErrorCode.FILE_ERROR

    def test_handle_error_logs_error(self):
        """Test that handle_error() logs errors."""
        handler = ErrorHandler(enable_logging=True, log_sensitive=False)
        
        with patch("homeconnect_coffee.errors.logger") as mock_logger:
            exception = ValueError("Test")
            handler.handle_error(exception)
            
            # Check that logger.warning was called
            assert mock_logger.log.called

    def test_handle_error_no_logging_when_disabled(self):
        """Test that handle_error() does not log when logging is disabled."""
        handler = ErrorHandler(enable_logging=False)
        
        with patch("homeconnect_coffee.errors.logger") as mock_logger:
            exception = ValueError("Test")
            handler.handle_error(exception)
            
            # Logger should not be called
            assert not mock_logger.log.called

    def test_classify_error_value_error(self):
        """Test _classify_error() with ValueError."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = ValueError("Ungültig")
        code, message, error_code = handler._classify_error(
            exception, 500, "Standard"
        )
        
        assert code == ErrorCode.BAD_REQUEST
        assert "Invalid parameter" in message
        assert error_code == ErrorCode.VALIDATION_ERROR

    def test_classify_error_file_not_found(self):
        """Test _classify_error() with FileNotFoundError."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = FileNotFoundError("Datei fehlt")
        code, message, error_code = handler._classify_error(
            exception, 500, "Standard"
        )
        
        assert code == ErrorCode.NOT_FOUND
        assert message == "Datei fehlt"
        assert error_code == ErrorCode.FILE_ERROR

