"""Unit-Tests für HTTP-Handler."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import Mock, patch

import pytest

from homeconnect_coffee.errors import ErrorCode, ErrorHandler
from homeconnect_coffee.handlers import (
    BaseHandler,
    CoffeeHandler,
    DashboardHandler,
    HistoryHandler,
    RequestRouter,
    StatusHandler,
)


@pytest.fixture
def mock_request():
    """Erstellt einen Mock-HTTP-Request."""
    request = Mock()
    request.makefile.return_value = BytesIO()
    return request


@pytest.fixture
def mock_server():
    """Erstellt einen Mock-HTTP-Server."""
    return Mock()


@pytest.fixture
def handler_kwargs(mock_request, mock_server):
    """Erstellt Standard-Kwargs für Handler."""
    return {
        "request": mock_request,
        "client_address": ("127.0.0.1", 12345),
        "server": mock_server,
    }


@pytest.fixture
def error_handler():
    """Erstellt einen ErrorHandler für Tests."""
    return ErrorHandler(enable_logging=False)


@pytest.mark.unit
class TestBaseHandler:
    """Tests für BaseHandler Klasse."""

    def test_mask_token_in_path(self, handler_kwargs):
        """Test _mask_token_in_path() maskiert Token."""
        handler = BaseHandler(**handler_kwargs)
        handler.path = "/test?token=secret123"
        
        masked = handler._mask_token_in_path(handler.path)
        
        assert "__MASKED__" in masked
        assert "secret123" not in masked

    def test_check_auth_no_token_configured(self, handler_kwargs):
        """Test _check_auth() wenn kein Token konfiguriert."""
        handler = BaseHandler(**handler_kwargs)
        handler.api_token = None
        
        assert handler._check_auth() is True

    def test_check_auth_valid_header(self, handler_kwargs):
        """Test _check_auth() mit gültigem Header-Token."""
        handler = BaseHandler(**handler_kwargs)
        handler.api_token = "test-token"
        handler.headers = Mock()
        handler.headers.get.return_value = "Bearer test-token"
        
        assert handler._check_auth() is True

    def test_check_auth_invalid_header(self, handler_kwargs):
        """Test _check_auth() mit ungültigem Header-Token."""
        handler = BaseHandler(**handler_kwargs)
        handler.api_token = "test-token"
        handler.headers = Mock()
        handler.headers.get.return_value = "Bearer wrong-token"
        handler.path = "/test"
        
        assert handler._check_auth() is False

    def test_check_auth_valid_query(self, handler_kwargs):
        """Test _check_auth() mit gültigem Query-Token."""
        handler = BaseHandler(**handler_kwargs)
        handler.api_token = "test-token"
        handler.path = "/test?token=test-token"
        handler.headers = {}
        
        assert handler._check_auth() is True

    def test_require_auth_sends_401(self, handler_kwargs, error_handler):
        """Test _require_auth() sendet 401 bei fehlender Auth."""
        handler = BaseHandler(**handler_kwargs)
        handler.api_token = "test-token"
        handler.error_handler = error_handler
        handler.path = "/test"
        handler.headers = Mock()
        handler.headers.get.return_value = ""
        handler.wfile = BytesIO()
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        result = handler._require_auth()
        
        assert result is False
        assert handler.send_response.called  # Response wurde gesendet

    def test_parse_path(self, handler_kwargs):
        """Test _parse_path() parst Pfad und Query-Parameter."""
        handler = BaseHandler(**handler_kwargs)
        handler.path = "/test?key=value&other=123"
        
        path, query_params = handler._parse_path()
        
        assert path == "/test"
        assert query_params["key"] == ["value"]
        assert query_params["other"] == ["123"]


@pytest.mark.unit
class TestCoffeeHandler:
    """Tests für CoffeeHandler Klasse."""

    def test_handle_wake(self, handler_kwargs, error_handler):
        """Test handle_wake() statische Methode."""
        router = BaseHandler(**handler_kwargs)
        router.path = "/wake"
        router.api_token = None  # Keine Auth für Test
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.send_response = Mock()
        router.send_header = Mock()
        router.end_headers = Mock()
        router.headers = Mock()
        router.headers.get.return_value = ""
        
        with patch("homeconnect_coffee.handlers.coffee_handler.load_config") as mock_config, \
             patch("homeconnect_coffee.handlers.coffee_handler.HomeConnectClient") as mock_client_class, \
             patch("homeconnect_coffee.handlers.coffee_handler.CoffeeService") as mock_service_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_service = Mock()
            mock_service.wake_device.return_value = {"status": "ok"}
            mock_service_class.return_value = mock_service
            
            CoffeeHandler.handle_wake(router)
            
            mock_service.wake_device.assert_called_once()

    def test_handle_brew(self, handler_kwargs, error_handler):
        """Test handle_brew() statische Methode."""
        router = BaseHandler(**handler_kwargs)
        router.path = "/brew"
        router.api_token = None
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.send_response = Mock()
        router.send_header = Mock()
        router.end_headers = Mock()
        router.headers = Mock()
        router.headers.get.return_value = ""
        
        with patch("homeconnect_coffee.handlers.coffee_handler.load_config") as mock_config, \
             patch("homeconnect_coffee.handlers.coffee_handler.HomeConnectClient") as mock_client_class, \
             patch("homeconnect_coffee.handlers.coffee_handler.CoffeeService") as mock_service_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_service = Mock()
            mock_service.brew_espresso.return_value = {"status": "ok"}
            mock_service_class.return_value = mock_service
            
            CoffeeHandler.handle_brew(router, 100)
            
            mock_service.brew_espresso.assert_called_once_with(100)


@pytest.mark.unit
class TestStatusHandler:
    """Tests für StatusHandler Klasse."""

    def test_handle_status(self, handler_kwargs, error_handler):
        """Test handle_status() statische Methode."""
        router = BaseHandler(**handler_kwargs)
        router.path = "/status"
        router.api_token = None
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.send_response = Mock()
        router.send_header = Mock()
        router.end_headers = Mock()
        router.headers = Mock()
        router.headers.get.return_value = ""
        
        with patch("homeconnect_coffee.handlers.status_handler.load_config") as mock_config, \
             patch("homeconnect_coffee.handlers.status_handler.HomeConnectClient") as mock_client_class, \
             patch("homeconnect_coffee.handlers.status_handler.StatusService") as mock_service_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_service = Mock()
            mock_service.get_status.return_value = {"status": "ok"}
            mock_service_class.return_value = mock_service
            
            StatusHandler.handle_status(router)
            
            mock_service.get_status.assert_called_once()

    def test_handle_extended_status(self, handler_kwargs, error_handler):
        """Test handle_extended_status() statische Methode."""
        router = BaseHandler(**handler_kwargs)
        router.path = "/api/status"
        router.api_token = None
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.send_response = Mock()
        router.send_header = Mock()
        router.end_headers = Mock()
        router.headers = Mock()
        router.headers.get.return_value = ""
        
        with patch("homeconnect_coffee.handlers.status_handler.load_config") as mock_config, \
             patch("homeconnect_coffee.handlers.status_handler.HomeConnectClient") as mock_client_class, \
             patch("homeconnect_coffee.handlers.status_handler.StatusService") as mock_service_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_service = Mock()
            mock_service.get_extended_status.return_value = {"status": "ok"}
            mock_service_class.return_value = mock_service
            
            StatusHandler.handle_extended_status(router)
            
            mock_service.get_extended_status.assert_called_once()


@pytest.mark.unit
class TestHistoryHandler:
    """Tests für HistoryHandler Klasse."""

    def test_handle_history(self, handler_kwargs, error_handler, temp_history_db):
        """Test handle_history() statische Methode."""
        from homeconnect_coffee.history import HistoryManager
        import homeconnect_coffee.handlers.history_handler as history_module
        
        router = BaseHandler(**handler_kwargs)
        router.path = "/api/history"
        router.api_token = None
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.send_response = Mock()
        router.send_header = Mock()
        router.end_headers = Mock()
        
        # Setze history_manager im Modul
        history_module.history_manager = HistoryManager(temp_history_db)
        
        try:
            with patch("homeconnect_coffee.handlers.history_handler.HistoryService") as mock_service_class:
                mock_service = Mock()
                mock_service.get_history.return_value = []
                mock_service_class.return_value = mock_service
                
                HistoryHandler.handle_history(router, {})
                
                mock_service.get_history.assert_called_once()
        finally:
            history_module.history_manager = None

    def test_handle_api_stats(self, handler_kwargs, error_handler):
        """Test handle_api_stats() statische Methode."""
        router = BaseHandler(**handler_kwargs)
        router.path = "/api/stats"
        router.api_token = None
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.send_response = Mock()
        router.send_header = Mock()
        router.end_headers = Mock()
        
        with patch("homeconnect_coffee.handlers.history_handler.get_monitor") as mock_monitor:
            mock_monitor_instance = Mock()
            mock_monitor_instance.get_stats.return_value = {"calls": 0}
            mock_monitor.return_value = mock_monitor_instance
            
            HistoryHandler.handle_api_stats(router)
            
            mock_monitor_instance.get_stats.assert_called_once()


@pytest.mark.unit
class TestDashboardHandler:
    """Tests für DashboardHandler Klasse."""

    def test_handle_dashboard(self, handler_kwargs, error_handler):
        """Test handle_dashboard() statische Methode."""
        router = BaseHandler(**handler_kwargs)
        router.path = "/dashboard"
        router.api_token = None
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.send_response = Mock()
        router.send_header = Mock()
        router.end_headers = Mock()
        
        # Mock Path komplett - verwende side_effect für komplexe parent-Kette
        mock_dashboard = Mock()
        mock_dashboard.exists.return_value = True
        mock_dashboard.read_text.return_value = "<html>Dashboard</html>"
        
        # Erstelle Mock-Kette für parent.parent.parent.parent / "scripts" / "dashboard.html"
        mock_scripts = Mock()
        mock_scripts.__truediv__ = Mock(return_value=mock_dashboard)
        
        mock_parent4 = Mock()
        mock_parent4.__truediv__ = Mock(return_value=mock_scripts)
        
        mock_parent3 = Mock()
        mock_parent3.parent = mock_parent4
        
        mock_parent2 = Mock()
        mock_parent2.parent = mock_parent3
        
        mock_parent1 = Mock()
        mock_parent1.parent = mock_parent2
        
        mock_file_path = Mock()
        mock_file_path.parent = mock_parent1
        
        with patch("homeconnect_coffee.handlers.dashboard_handler.Path", return_value=mock_file_path):
            DashboardHandler.handle_dashboard(router)
            
            # Prüfe dass read_text aufgerufen wurde
            mock_dashboard.read_text.assert_called_once()
            # Prüfe dass send_response aufgerufen wurde
            router.send_response.assert_called_once_with(200)

    def test_handle_health(self, handler_kwargs, error_handler):
        """Test handle_health() statische Methode."""
        router = BaseHandler(**handler_kwargs)
        router.path = "/health"
        router.api_token = None
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.send_response = Mock()
        router.send_header = Mock()
        router.end_headers = Mock()
        
        DashboardHandler.handle_health(router)
        
        # Prüfe dass JSON gesendet wurde
        assert router.wfile.getvalue() == b'{\n  "status": "ok"\n}'


@pytest.mark.unit
class TestRequestRouter:
    """Tests für RequestRouter Klasse."""

    def test_route_coffee_handler(self, handler_kwargs, error_handler):
        """Test Router leitet /wake an CoffeeHandler weiter."""
        router = RequestRouter(**handler_kwargs)
        router.path = "/wake"
        router.command = "GET"
        router.enable_logging = False
        router.api_token = None
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.headers = Mock()
        router.rfile = BytesIO()
        
        with patch("homeconnect_coffee.handlers.router.CoffeeHandler.handle_wake") as mock_handle:
            router._route_request()
            mock_handle.assert_called_once_with(router)

    def test_route_status_handler(self, handler_kwargs, error_handler):
        """Test Router leitet /status an StatusHandler weiter."""
        router = RequestRouter(**handler_kwargs)
        router.path = "/status"
        router.command = "GET"
        router.enable_logging = False
        router.api_token = None
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.headers = Mock()
        router.rfile = BytesIO()
        
        with patch("homeconnect_coffee.handlers.router.StatusHandler.handle_status") as mock_handle:
            router._route_request()
            mock_handle.assert_called_once_with(router)

    def test_route_history_handler(self, handler_kwargs, error_handler):
        """Test Router leitet /api/history an HistoryHandler weiter."""
        router = RequestRouter(**handler_kwargs)
        router.path = "/api/history"
        router.command = "GET"
        router.enable_logging = False
        router.api_token = None
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.headers = Mock()
        router.rfile = BytesIO()
        
        with patch("homeconnect_coffee.handlers.router.HistoryHandler.handle_history") as mock_handle:
            router._route_request()
            mock_handle.assert_called_once()
            # Prüfe dass router und query_params übergeben wurden
            assert mock_handle.call_args[0][0] == router

    def test_route_dashboard_handler(self, handler_kwargs, error_handler):
        """Test Router leitet /dashboard an DashboardHandler weiter."""
        router = RequestRouter(**handler_kwargs)
        router.path = "/dashboard"
        router.command = "GET"
        router.enable_logging = False
        router.api_token = None
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.headers = Mock()
        router.rfile = BytesIO()
        
        with patch("homeconnect_coffee.handlers.router.DashboardHandler.handle_dashboard") as mock_handle:
            router._route_request()
            mock_handle.assert_called_once_with(router)

    def test_route_not_found(self, handler_kwargs, error_handler):
        """Test Router sendet 404 für unbekannte Pfade."""
        router = RequestRouter(**handler_kwargs)
        router.path = "/unknown"
        router.command = "GET"
        router.enable_logging = False
        router.api_token = None
        router.error_handler = error_handler
        router.wfile = BytesIO()
        router.headers = Mock()
        router.rfile = BytesIO()
        
        with patch.object(router, "_send_not_found") as mock_not_found:
            router._route_request()
            mock_not_found.assert_called_once()

