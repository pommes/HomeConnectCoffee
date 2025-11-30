"""Unit tests for services."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from homeconnect_coffee.services import CoffeeService, HistoryService, StatusService


@pytest.mark.unit
class TestCoffeeService:
    """Tests for CoffeeService."""

    def test_wake_device_activates(self, test_config, valid_token_bundle, temp_token_file):
        """Test wake_device() activates the device."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        
        client = HomeConnectClient(test_config)
        
        with patch.object(client, "set_setting") as mock_set_setting:
            mock_set_setting.return_value = {}
            
            service = CoffeeService(client)
            result = service.wake_device()
            
            assert result["status"] == "activated"
            assert "Device was activated" in result["message"]
            mock_set_setting.assert_called_once_with(
                "BSH.Common.Setting.PowerState",
                "BSH.Common.EnumType.PowerState.On"
            )

    def test_wake_device_already_on(self, test_config, valid_token_bundle, temp_token_file):
        """Test wake_device() detects when device is already active."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        
        client = HomeConnectClient(test_config)
        
        with patch.object(client, "set_setting") as mock_set_setting, \
             patch.object(client, "get_status") as mock_get_status, \
             patch.object(client, "get_settings") as mock_get_settings:
            
            # set_setting raises RuntimeError (device already active)
            mock_set_setting.side_effect = RuntimeError("Already on")
            
            # get_status returns OperationState != Inactive
            mock_get_status.return_value = {
                "data": {
                    "status": [
                        {
                            "key": "BSH.Common.Status.OperationState",
                            "value": "BSH.Common.EnumType.OperationState.Run"
                        }
                    ]
                }
            }
            
            service = CoffeeService(client)
            result = service.wake_device()
            
            assert result["status"] == "already_on"
            assert "already activated" in result["message"]

    def test_brew_espresso(self, test_config, valid_token_bundle, temp_token_file):
        """Test brew_espresso() starts espresso."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        
        client = HomeConnectClient(test_config)
        
        with patch.object(client, "get_settings") as mock_get_settings, \
             patch.object(client, "clear_selected_program") as mock_clear, \
             patch.object(client, "select_program") as mock_select, \
             patch.object(client, "start_program") as mock_start:
            
            # Mock Settings (device is already active)
            mock_get_settings.return_value = {
                "data": {
                    "settings": [
                        {
                            "key": "BSH.Common.Setting.PowerState",
                            "value": "BSH.Common.EnumType.PowerState.On"
                        }
                    ]
                }
            }
            
            service = CoffeeService(client)
            result = service.brew_espresso(50)
            
            assert result["status"] == "started"
            assert "Espresso (50 ml)" in result["message"]
            
            # Check that program was selected and started
            mock_select.assert_called_once()
            mock_start.assert_called_once()

    def test_brew_espresso_activates_device(self, test_config, valid_token_bundle, temp_token_file):
        """Test brew_espresso() activates device if necessary."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        
        client = HomeConnectClient(test_config)
        
        with patch.object(client, "get_settings") as mock_get_settings, \
             patch.object(client, "set_setting") as mock_set_setting, \
             patch.object(client, "clear_selected_program") as mock_clear, \
             patch.object(client, "select_program") as mock_select, \
             patch.object(client, "start_program") as mock_start:
            
            # Mock Settings (device is in standby)
            mock_get_settings.return_value = {
                "data": {
                    "settings": [
                        {
                            "key": "BSH.Common.Setting.PowerState",
                            "value": "BSH.Common.EnumType.PowerState.Standby"
                        }
                    ]
                }
            }
            
            service = CoffeeService(client)
            service.brew_espresso(50)
            
            # Check that device was activated
            mock_set_setting.assert_called_once_with(
                "BSH.Common.Setting.PowerState",
                "BSH.Common.EnumType.PowerState.On"
            )

    def test_brew_program_espresso(self, test_config, valid_token_bundle, temp_token_file):
        """Test brew_program() with espresso."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        from homeconnect_coffee.services.coffee_service import ESPRESSO_KEY
        
        client = HomeConnectClient(test_config)
        
        with patch.object(client, "get_settings") as mock_get_settings, \
             patch.object(client, "clear_selected_program") as mock_clear, \
             patch.object(client, "select_program") as mock_select, \
             patch.object(client, "start_program") as mock_start:
            
            mock_get_settings.return_value = {
                "data": {
                    "settings": [
                        {
                            "key": "BSH.Common.Setting.PowerState",
                            "value": "BSH.Common.EnumType.PowerState.On"
                        }
                    ]
                }
            }
            
            service = CoffeeService(client)
            result = service.brew_program(ESPRESSO_KEY, fill_ml=50, program_name="Espresso")
            
            assert result["status"] == "started"
            assert "Espresso (50 ml)" in result["message"]
            mock_select.assert_called_once()
            mock_start.assert_called_once()

    def test_brew_program_cappuccino(self, test_config, valid_token_bundle, temp_token_file):
        """Test brew_program() with cappuccino (no fill_ml)."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        from homeconnect_coffee.services.coffee_service import CAPPUCCINO_KEY
        
        client = HomeConnectClient(test_config)
        
        with patch.object(client, "get_settings") as mock_get_settings, \
             patch.object(client, "clear_selected_program") as mock_clear, \
             patch.object(client, "select_program") as mock_select, \
             patch.object(client, "start_program") as mock_start:
            
            mock_get_settings.return_value = {
                "data": {
                    "settings": [
                        {
                            "key": "BSH.Common.Setting.PowerState",
                            "value": "BSH.Common.EnumType.PowerState.On"
                        }
                    ]
                }
            }
            
            service = CoffeeService(client)
            result = service.brew_program(CAPPUCCINO_KEY, fill_ml=None, program_name="Cappuccino")
            
            assert result["status"] == "started"
            assert "Cappuccino" in result["message"]
            assert "ml" not in result["message"]  # No fill_ml for cappuccino
            mock_select.assert_called_once()
            mock_start.assert_called_once()

    def test_brew_program_invalid_fill_ml(self, test_config, valid_token_bundle, temp_token_file):
        """Test brew_program() raises ValueError for fill_ml on unsupported program."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        from homeconnect_coffee.services.coffee_service import CAPPUCCINO_KEY
        
        client = HomeConnectClient(test_config)
        service = CoffeeService(client)
        
        with pytest.raises(ValueError, match="does not support fill_ml"):
            service.brew_program(CAPPUCCINO_KEY, fill_ml=200, program_name="cappuccino")


@pytest.mark.unit
class TestStatusService:
    """Tests for StatusService."""

    def test_get_status(self, test_config, valid_token_bundle, temp_token_file):
        """Test get_status() returns status."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        
        client = HomeConnectClient(test_config)
        
        expected_status = {"data": {"status": []}}
        
        with patch.object(client, "get_status", return_value=expected_status):
            service = StatusService(client)
            result = service.get_status()
            
            assert result == expected_status

    def test_get_extended_status(self, test_config, valid_token_bundle, temp_token_file):
        """Test get_extended_status() returns extended status."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        
        client = HomeConnectClient(test_config)
        
        with patch.object(client, "get_status") as mock_status, \
             patch.object(client, "get_settings") as mock_settings, \
             patch.object(client, "get_programs") as mock_programs, \
             patch.object(client, "get_selected_program") as mock_selected, \
             patch.object(client, "get_active_program") as mock_active:
            
            mock_status.return_value = {"data": {"status": []}}
            mock_settings.return_value = {"data": {"settings": []}}
            mock_programs.return_value = {"data": {"programs": []}}
            mock_selected.return_value = {"data": {}}
            mock_active.return_value = {"data": {}}
            
            service = StatusService(client)
            result = service.get_extended_status()
            
            assert "status" in result
            assert "settings" in result
            assert "programs" in result
            assert "available" in result["programs"]
            assert "selected" in result["programs"]
            assert "active" in result["programs"]

    def test_get_extended_status_handles_errors(self, test_config, valid_token_bundle, temp_token_file):
        """Test get_extended_status() handles errors for programs."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        
        client = HomeConnectClient(test_config)
        
        with patch.object(client, "get_status") as mock_status, \
             patch.object(client, "get_settings") as mock_settings, \
             patch.object(client, "get_programs") as mock_programs, \
             patch.object(client, "get_selected_program") as mock_selected, \
             patch.object(client, "get_active_program") as mock_active:
            
            mock_status.return_value = {"data": {"status": []}}
            mock_settings.return_value = {"data": {"settings": []}}
            # Programs can fail
            mock_programs.side_effect = RuntimeError("Not ready")
            mock_selected.side_effect = RuntimeError("Not ready")
            mock_active.side_effect = RuntimeError("Not ready")
            
            service = StatusService(client)
            result = service.get_extended_status()
            
            # Should still return status and settings
            assert "status" in result
            assert "settings" in result
            # Programs should be empty dicts
            assert result["programs"]["available"] == {}
            assert result["programs"]["selected"] == {}
            assert result["programs"]["active"] == {}


@pytest.mark.unit
class TestHistoryService:
    """Tests for HistoryService."""

    def test_get_history(self, temp_history_db):
        """Test get_history() returns history."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        manager.add_event("test_event", {"data": "test"})
        
        service = HistoryService(manager)
        history = service.get_history()
        
        assert len(history) == 1
        assert history[0]["type"] == "test_event"

    def test_get_history_with_filters(self, temp_history_db):
        """Test get_history() with filters."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        manager.add_event("type1", {"data": 1})
        manager.add_event("type2", {"data": 2})
        manager.add_event("type1", {"data": 3})
        
        service = HistoryService(manager)
        history = service.get_history(event_type="type1")
        
        assert len(history) == 2
        assert all(event["type"] == "type1" for event in history)

    def test_get_program_counts(self, temp_history_db):
        """Test get_program_counts()."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        manager.add_event("program_started", {"program": "Espresso"})
        manager.add_event("program_started", {"program": "Cappuccino"})
        manager.add_event("program_started", {"program": "Espresso"})
        
        service = HistoryService(manager)
        counts = service.get_program_counts()
        
        assert counts["Espresso"] == 2
        assert counts["Cappuccino"] == 1

    def test_get_daily_usage(self, temp_history_db):
        """Test get_daily_usage()."""
        from datetime import datetime, timezone
        
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        
        # Füge Events für verschiedene Tage hinzu
        today = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
        manager.add_event("program_started", {"program": "Espresso"}, timestamp=today)
        manager.add_event("program_started", {"program": "Cappuccino"}, timestamp=today)
        
        service = HistoryService(manager)
        usage = service.get_daily_usage(days=7)
        
        assert len(usage) == 7
        today_key = today.strftime("%Y-%m-%d")
        assert usage.get(today_key, 0) == 2

