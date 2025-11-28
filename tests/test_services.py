"""Unit-Tests für Services."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from homeconnect_coffee.services import CoffeeService, HistoryService, StatusService


@pytest.mark.unit
class TestCoffeeService:
    """Tests für CoffeeService."""

    def test_wake_device_activates(self, test_config, valid_token_bundle, temp_token_file):
        """Test wake_device() aktiviert das Gerät."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        
        client = HomeConnectClient(test_config)
        
        with patch.object(client, "set_setting") as mock_set_setting:
            mock_set_setting.return_value = {}
            
            service = CoffeeService(client)
            result = service.wake_device()
            
            assert result["status"] == "activated"
            assert "Gerät wurde aktiviert" in result["message"]
            mock_set_setting.assert_called_once_with(
                "BSH.Common.Setting.PowerState",
                "BSH.Common.EnumType.PowerState.On"
            )

    def test_wake_device_already_on(self, test_config, valid_token_bundle, temp_token_file):
        """Test wake_device() erkennt wenn Gerät bereits aktiv ist."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        
        client = HomeConnectClient(test_config)
        
        with patch.object(client, "set_setting") as mock_set_setting, \
             patch.object(client, "get_status") as mock_get_status, \
             patch.object(client, "get_settings") as mock_get_settings:
            
            # set_setting wirft RuntimeError (Gerät bereits aktiv)
            mock_set_setting.side_effect = RuntimeError("Already on")
            
            # get_status gibt OperationState != Inactive zurück
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
            assert "bereits aktiviert" in result["message"]

    def test_brew_espresso(self, test_config, valid_token_bundle, temp_token_file):
        """Test brew_espresso() startet Espresso."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        
        client = HomeConnectClient(test_config)
        
        with patch.object(client, "get_settings") as mock_get_settings, \
             patch.object(client, "clear_selected_program") as mock_clear, \
             patch.object(client, "select_program") as mock_select, \
             patch.object(client, "start_program") as mock_start:
            
            # Mock Settings (Gerät ist bereits aktiv)
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
            
            # Prüfe dass Programm ausgewählt und gestartet wurde
            mock_select.assert_called_once()
            mock_start.assert_called_once()

    def test_brew_espresso_activates_device(self, test_config, valid_token_bundle, temp_token_file):
        """Test brew_espresso() aktiviert Gerät falls nötig."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        
        client = HomeConnectClient(test_config)
        
        with patch.object(client, "get_settings") as mock_get_settings, \
             patch.object(client, "set_setting") as mock_set_setting, \
             patch.object(client, "clear_selected_program") as mock_clear, \
             patch.object(client, "select_program") as mock_select, \
             patch.object(client, "start_program") as mock_start:
            
            # Mock Settings (Gerät ist im Standby)
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
            
            # Prüfe dass Gerät aktiviert wurde
            mock_set_setting.assert_called_once_with(
                "BSH.Common.Setting.PowerState",
                "BSH.Common.EnumType.PowerState.On"
            )


@pytest.mark.unit
class TestStatusService:
    """Tests für StatusService."""

    def test_get_status(self, test_config, valid_token_bundle, temp_token_file):
        """Test get_status() gibt Status zurück."""
        valid_token_bundle.save(temp_token_file)
        
        from homeconnect_coffee.client import HomeConnectClient
        
        client = HomeConnectClient(test_config)
        
        expected_status = {"data": {"status": []}}
        
        with patch.object(client, "get_status", return_value=expected_status):
            service = StatusService(client)
            result = service.get_status()
            
            assert result == expected_status

    def test_get_extended_status(self, test_config, valid_token_bundle, temp_token_file):
        """Test get_extended_status() gibt erweiterten Status zurück."""
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
        """Test get_extended_status() behandelt Fehler bei Programmen."""
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
            # Programme können fehlschlagen
            mock_programs.side_effect = RuntimeError("Not ready")
            mock_selected.side_effect = RuntimeError("Not ready")
            mock_active.side_effect = RuntimeError("Not ready")
            
            service = StatusService(client)
            result = service.get_extended_status()
            
            # Sollte trotzdem Status und Settings zurückgeben
            assert "status" in result
            assert "settings" in result
            # Programme sollten leere Dicts sein
            assert result["programs"]["available"] == {}
            assert result["programs"]["selected"] == {}
            assert result["programs"]["active"] == {}


@pytest.mark.unit
class TestHistoryService:
    """Tests für HistoryService."""

    def test_get_history(self, temp_history_db):
        """Test get_history() gibt History zurück."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        manager.add_event("test_event", {"data": "test"})
        
        service = HistoryService(manager)
        history = service.get_history()
        
        assert len(history) == 1
        assert history[0]["type"] == "test_event"

    def test_get_history_with_filters(self, temp_history_db):
        """Test get_history() mit Filtern."""
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

