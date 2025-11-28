"""Unit tests for AuthMiddleware."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import Mock

import pytest

from homeconnect_coffee.errors import ErrorCode, ErrorHandler
from homeconnect_coffee.handlers import BaseHandler
from homeconnect_coffee.middleware import AuthMiddleware


@pytest.fixture
def mock_request():
    """Creates a mock HTTP request."""
    request = Mock()
    request.makefile.return_value = BytesIO()
    return request


@pytest.fixture
def mock_server():
    """Creates a mock HTTP server."""
    return Mock()


@pytest.fixture
def handler_kwargs(mock_request, mock_server):
    """Creates standard kwargs for handlers."""
    return {
        "request": mock_request,
        "client_address": ("127.0.0.1", 12345),
        "server": mock_server,
    }


@pytest.fixture
def error_handler():
    """Creates an ErrorHandler for tests."""
    return ErrorHandler(enable_logging=False)


@pytest.mark.unit
class TestAuthMiddleware:
    """Tests for AuthMiddleware class."""

    def test_check_auth_no_token_configured(self, handler_kwargs):
        """Test check_auth() when no token is configured."""
        middleware = AuthMiddleware(api_token=None)
        router = BaseHandler(**handler_kwargs)
        router.path = "/test"
        router.headers = Mock()
        
        assert middleware.check_auth(router) is True

    def test_check_auth_valid_header(self, handler_kwargs):
        """Test check_auth() with valid header token."""
        middleware = AuthMiddleware(api_token="test-token")
        router = BaseHandler(**handler_kwargs)
        router.path = "/test"
        router.headers = Mock()
        router.headers.get.return_value = "Bearer test-token"
        
        assert middleware.check_auth(router) is True

    def test_check_auth_invalid_header(self, handler_kwargs):
        """Test check_auth() with invalid header token."""
        middleware = AuthMiddleware(api_token="test-token")
        router = BaseHandler(**handler_kwargs)
        router.path = "/test"
        router.headers = Mock()
        router.headers.get.return_value = "Bearer wrong-token"
        
        assert middleware.check_auth(router) is False

    def test_check_auth_valid_query(self, handler_kwargs):
        """Test check_auth() with valid query token."""
        middleware = AuthMiddleware(api_token="test-token")
        router = BaseHandler(**handler_kwargs)
        router.path = "/test?token=test-token"
        router.headers = Mock()
        router.headers.get.return_value = ""
        
        assert middleware.check_auth(router) is True

    def test_check_auth_invalid_query(self, handler_kwargs):
        """Test check_auth() with invalid query token."""
        middleware = AuthMiddleware(api_token="test-token")
        router = BaseHandler(**handler_kwargs)
        router.path = "/test?token=wrong-token"
        router.headers = Mock()
        router.headers.get.return_value = ""
        
        assert middleware.check_auth(router) is False

    def test_require_auth_sends_401(self, handler_kwargs, error_handler):
        """Test require_auth() sends 401 on missing auth."""
        middleware = AuthMiddleware(api_token="test-token", error_handler=error_handler)
        router = BaseHandler(**handler_kwargs)
        router.path = "/test"
        router.headers = Mock()
        router.headers.get.return_value = ""
        router.wfile = BytesIO()
        router.send_response = Mock()
        router.send_header = Mock()
        router.end_headers = Mock()
        
        result = middleware.require_auth(router)
        
        assert result is False
        assert router.send_response.called  # Response wurde gesendet

    def test_require_auth_success(self, handler_kwargs, error_handler):
        """Test require_auth() returns True on successful auth."""
        middleware = AuthMiddleware(api_token="test-token", error_handler=error_handler)
        router = BaseHandler(**handler_kwargs)
        router.path = "/test?token=test-token"
        router.headers = Mock()
        router.headers.get.return_value = ""
        
        result = middleware.require_auth(router)
        
        assert result is True

    def test_middleware_as_callable(self, handler_kwargs, error_handler):
        """Test middleware can be used as callable."""
        middleware = AuthMiddleware(api_token="test-token", error_handler=error_handler)
        router = BaseHandler(**handler_kwargs)
        router.path = "/test?token=test-token"
        router.headers = Mock()
        router.headers.get.return_value = ""
        
        result = middleware(router)
        
        assert result is True

    def test_require_auth_no_error_handler(self, handler_kwargs):
        """Test require_auth() without ErrorHandler uses legacy method."""
        middleware = AuthMiddleware(api_token="test-token", error_handler=None)
        router = BaseHandler(**handler_kwargs)
        router.path = "/test"
        router.headers = Mock()
        router.headers.get.return_value = ""
        router.wfile = BytesIO()
        router.send_response = Mock()
        router.send_header = Mock()
        router.end_headers = Mock()
        
        result = middleware.require_auth(router)
        
        assert result is False
        assert router.send_response.called  # Response wurde gesendet

