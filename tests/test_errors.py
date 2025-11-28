"""Unit-Tests für errors.py (ErrorHandler)."""

from __future__ import annotations

import logging
from unittest.mock import Mock, patch

import pytest
import requests

from homeconnect_coffee.errors import ErrorCode, ErrorHandler


@pytest.mark.unit
class TestErrorHandler:
    """Tests für ErrorHandler Klasse."""

    def test_init(self):
        """Test dass __init__ den Handler korrekt initialisiert."""
        handler = ErrorHandler(enable_logging=False)
        
        assert handler.enable_logging is False
        assert handler.log_sensitive is False

    def test_init_with_logging(self):
        """Test __init__ mit Logging aktiviert."""
        handler = ErrorHandler(enable_logging=True, log_sensitive=True)
        
        assert handler.enable_logging is True
        assert handler.log_sensitive is True

    def test_format_error_response(self):
        """Test format_error_response() erstellt korrektes Format."""
        handler = ErrorHandler(enable_logging=False)
        
        response = handler.format_error_response(500, "Test-Fehler")
        
        assert response["error"] == "Test-Fehler"
        assert response["code"] == 500
        assert "error_code" not in response

    def test_format_error_response_with_error_code(self):
        """Test format_error_response() mit Error-Code."""
        handler = ErrorHandler(enable_logging=False)
        
        response = handler.format_error_response(
            500, "Test-Fehler", error_code=ErrorCode.INTERNAL_SERVER_ERROR
        )
        
        assert response["error"] == "Test-Fehler"
        assert response["code"] == 500
        assert response["error_code"] == ErrorCode.INTERNAL_SERVER_ERROR

    def test_format_error_response_with_details(self):
        """Test format_error_response() mit Details."""
        handler = ErrorHandler(enable_logging=False)
        
        response = handler.format_error_response(
            500, "Test-Fehler", details={"field": "value"}
        )
        
        assert response["error"] == "Test-Fehler"
        assert response["code"] == 500
        assert response["details"] == {"field": "value"}

    def test_handle_error_value_error(self):
        """Test handle_error() mit ValueError."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = ValueError("Ungültiger Wert")
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.BAD_REQUEST
        assert response["error"] == "Ungültiger Parameter: Ungültiger Wert"
        assert response["code"] == ErrorCode.BAD_REQUEST
        assert response["error_code"] == ErrorCode.VALIDATION_ERROR

    def test_handle_error_file_not_found(self):
        """Test handle_error() mit FileNotFoundError."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = FileNotFoundError("Datei nicht gefunden")
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.NOT_FOUND
        assert response["error"] == "Datei nicht gefunden"
        assert response["code"] == ErrorCode.NOT_FOUND
        assert response["error_code"] == ErrorCode.FILE_ERROR

    def test_handle_error_timeout(self):
        """Test handle_error() mit Timeout."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = requests.exceptions.Timeout("Request timeout")
        exception.__class__.__name__ = "Timeout"  # Mock für Typ-Prüfung
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.GATEWAY_TIMEOUT
        assert response["error"] == "API-Anfrage hat das Timeout überschritten"
        assert response["code"] == ErrorCode.GATEWAY_TIMEOUT
        assert response["error_code"] == ErrorCode.API_ERROR

    def test_handle_error_http_error_401(self):
        """Test handle_error() mit HTTPError 401."""
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
        """Test handle_error() mit HTTPError 429 (Rate Limit)."""
        handler = ErrorHandler(enable_logging=False)
        
        response_mock = Mock()
        response_mock.status_code = 429
        
        exception = requests.exceptions.HTTPError("Too Many Requests")
        exception.response = response_mock
        exception.__class__.__name__ = "HTTPError"
        
        code, response = handler.handle_error(exception)
        
        assert code == ErrorCode.GATEWAY_TIMEOUT
        assert "Rate-Limit" in response["error"]
        assert response["code"] == ErrorCode.GATEWAY_TIMEOUT
        assert response["error_code"] == ErrorCode.API_ERROR

    def test_handle_error_generic_exception(self):
        """Test handle_error() mit generischer Exception."""
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
        """Test handle_error() mit Traceback (nur wenn log_sensitive=True)."""
        handler = ErrorHandler(enable_logging=False, log_sensitive=True)
        
        exception = RuntimeError("Test")
        code, response = handler.handle_error(
            exception,
            include_traceback=True,
        )
        
        # Traceback sollte enthalten sein, wenn log_sensitive=True
        assert "traceback" in response

    def test_handle_error_without_traceback(self):
        """Test handle_error() ohne Traceback (wenn log_sensitive=False)."""
        handler = ErrorHandler(enable_logging=False, log_sensitive=False)
        
        exception = RuntimeError("Test")
        code, response = handler.handle_error(
            exception,
            include_traceback=True,
        )
        
        # Traceback sollte NICHT enthalten sein, wenn log_sensitive=False
        assert "traceback" not in response

    def test_create_error_response(self):
        """Test create_error_response() für manuelle Fehler."""
        handler = ErrorHandler(enable_logging=False)
        
        response = handler.create_error_response(
            ErrorCode.NOT_FOUND,
            "Ressource nicht gefunden",
            ErrorCode.FILE_ERROR,
        )
        
        assert response["error"] == "Ressource nicht gefunden"
        assert response["code"] == ErrorCode.NOT_FOUND
        assert response["error_code"] == ErrorCode.FILE_ERROR

    def test_handle_error_logs_error(self):
        """Test dass handle_error() Fehler loggt."""
        handler = ErrorHandler(enable_logging=True, log_sensitive=False)
        
        with patch("homeconnect_coffee.errors.logger") as mock_logger:
            exception = ValueError("Test")
            handler.handle_error(exception)
            
            # Prüfe dass logger.warning aufgerufen wurde
            assert mock_logger.log.called

    def test_handle_error_no_logging_when_disabled(self):
        """Test dass handle_error() nicht loggt, wenn Logging deaktiviert."""
        handler = ErrorHandler(enable_logging=False)
        
        with patch("homeconnect_coffee.errors.logger") as mock_logger:
            exception = ValueError("Test")
            handler.handle_error(exception)
            
            # Logger sollte nicht aufgerufen werden
            assert not mock_logger.log.called

    def test_classify_error_value_error(self):
        """Test _classify_error() mit ValueError."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = ValueError("Ungültig")
        code, message, error_code = handler._classify_error(
            exception, 500, "Standard"
        )
        
        assert code == ErrorCode.BAD_REQUEST
        assert "Ungültiger Parameter" in message
        assert error_code == ErrorCode.VALIDATION_ERROR

    def test_classify_error_file_not_found(self):
        """Test _classify_error() mit FileNotFoundError."""
        handler = ErrorHandler(enable_logging=False)
        
        exception = FileNotFoundError("Datei fehlt")
        code, message, error_code = handler._classify_error(
            exception, 500, "Standard"
        )
        
        assert code == ErrorCode.NOT_FOUND
        assert message == "Datei fehlt"
        assert error_code == ErrorCode.FILE_ERROR

