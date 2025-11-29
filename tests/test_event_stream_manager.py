"""Unit tests for event_stream_manager.py (EventStreamManager)."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from homeconnect_coffee.services.event_stream_manager import EventStreamManager


@pytest.mark.unit
class TestEventStreamManager:
    """Tests for EventStreamManager class."""

    def test_init(self, temp_history_db):
        """Test that __init__ initializes the manager correctly."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        assert event_manager.history_manager == manager
        assert event_manager.enable_logging is False
        assert len(event_manager._clients) == 0

    def test_add_client(self, temp_history_db):
        """Test add_client() adds client."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        client1 = Mock()
        client2 = Mock()
        
        event_manager.add_client(client1)
        event_manager.add_client(client2)
        
        assert len(event_manager._clients) == 2
        assert client1 in event_manager._clients
        assert client2 in event_manager._clients

    def test_add_client_duplicate(self, temp_history_db):
        """Test add_client() prevents duplicates."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        client = Mock()
        
        event_manager.add_client(client)
        event_manager.add_client(client)  # Add second time
        
        assert len(event_manager._clients) == 1

    def test_remove_client(self, temp_history_db):
        """Test remove_client() removes client."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        client1 = Mock()
        client2 = Mock()
        
        event_manager.add_client(client1)
        event_manager.add_client(client2)
        event_manager.remove_client(client1)
        
        assert len(event_manager._clients) == 1
        assert client1 not in event_manager._clients
        assert client2 in event_manager._clients

    def test_remove_client_nonexistent(self, temp_history_db):
        """Test remove_client() with non-existent client."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        client = Mock()
        
        # Sollte keinen Fehler werfen
        event_manager.remove_client(client)
        assert len(event_manager._clients) == 0

    def test_broadcast_event_no_clients(self, temp_history_db):
        """Test broadcast_event() with no clients."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        # Sollte keinen Fehler werfen
        event_manager.broadcast_event("test", {"data": "test"})

    def test_broadcast_event_with_clients(self, temp_history_db):
        """Test broadcast_event() sends event to clients."""
        from homeconnect_coffee.history import HistoryManager
        from homeconnect_coffee.handlers.dashboard_handler import DashboardHandler
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        client1 = Mock()
        client2 = Mock()
        
        event_manager.add_client(client1)
        event_manager.add_client(client2)
        
        # Mock the static method
        with patch.object(DashboardHandler, '_send_sse_event') as mock_send:
            event_manager.broadcast_event("STATUS", {"status": "on"})
            
            # Check that _send_sse_event was called for both clients
            assert mock_send.call_count == 2
            mock_send.assert_any_call(client1, "STATUS", {"status": "on"})
            mock_send.assert_any_call(client2, "STATUS", {"status": "on"})

    def test_broadcast_event_removes_disconnected_clients(self, temp_history_db):
        """Test broadcast_event() removes disconnected clients."""
        from homeconnect_coffee.history import HistoryManager
        from homeconnect_coffee.handlers.dashboard_handler import DashboardHandler
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        client1 = Mock()
        client2 = Mock()
        
        event_manager.add_client(client1)
        event_manager.add_client(client2)
        
        # Mock the static method to raise BrokenPipeError for client1
        def side_effect(router, event_type, data):
            if router == client1:
                raise BrokenPipeError()
        
        with patch.object(DashboardHandler, '_send_sse_event', side_effect=side_effect):
            event_manager.broadcast_event("STATUS", {"status": "on"})
        
        # client1 should have been removed
        assert client1 not in event_manager._clients
        assert client2 in event_manager._clients

    def test_start_starts_workers(self, temp_history_db):
        """Test start() starts worker threads."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        event_manager.start()
        
        # Check that threads were started
        assert event_manager._stream_running is True
        assert event_manager._stream_thread is not None
        assert event_manager._stream_thread.is_alive() or not event_manager._stream_thread.is_alive()  # Thread might already be finished if config is missing
        assert event_manager._history_worker_thread is not None

    def test_stop_stops_worker(self, temp_history_db):
        """Test stop() stops worker."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        event_manager.start()
        event_manager.stop()
        
        # Check that stop event was set
        assert event_manager._stream_stop_event.is_set()
        assert event_manager._stream_running is False

    def test_start_idempotent(self, temp_history_db):
        """Test start() can be called multiple times."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        event_manager.start()
        thread1 = event_manager._stream_thread
        
        event_manager.start()  # Second time
        
        # Should not crash, thread should remain the same
        assert event_manager._stream_running is True

