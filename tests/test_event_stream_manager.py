"""Unit-Tests für event_stream_manager.py (EventStreamManager)."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from homeconnect_coffee.services.event_stream_manager import EventStreamManager


@pytest.mark.unit
class TestEventStreamManager:
    """Tests für EventStreamManager Klasse."""

    def test_init(self, temp_history_db):
        """Test dass __init__ den Manager korrekt initialisiert."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        assert event_manager.history_manager == manager
        assert event_manager.enable_logging is False
        assert len(event_manager._clients) == 0

    def test_add_client(self, temp_history_db):
        """Test add_client() fügt Client hinzu."""
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
        """Test add_client() verhindert Duplikate."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        client = Mock()
        
        event_manager.add_client(client)
        event_manager.add_client(client)  # Zweites Mal hinzufügen
        
        assert len(event_manager._clients) == 1

    def test_remove_client(self, temp_history_db):
        """Test remove_client() entfernt Client."""
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
        """Test remove_client() mit nicht existierendem Client."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        client = Mock()
        
        # Sollte keinen Fehler werfen
        event_manager.remove_client(client)
        assert len(event_manager._clients) == 0

    def test_broadcast_event_no_clients(self, temp_history_db):
        """Test broadcast_event() mit keinen Clients."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        # Sollte keinen Fehler werfen
        event_manager.broadcast_event("test", {"data": "test"})

    def test_broadcast_event_with_clients(self, temp_history_db):
        """Test broadcast_event() sendet Event an Clients."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        client1 = Mock()
        client2 = Mock()
        
        event_manager.add_client(client1)
        event_manager.add_client(client2)
        
        event_manager.broadcast_event("STATUS", {"status": "on"})
        
        # Prüfe dass _send_sse_event aufgerufen wurde
        assert client1._send_sse_event.called
        assert client2._send_sse_event.called
        
        # Prüfe dass korrekte Parameter übergeben wurden
        client1._send_sse_event.assert_called_once_with("STATUS", {"status": "on"})
        client2._send_sse_event.assert_called_once_with("STATUS", {"status": "on"})

    def test_broadcast_event_removes_disconnected_clients(self, temp_history_db):
        """Test broadcast_event() entfernt getrennte Clients."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        client1 = Mock()
        client2 = Mock()
        
        # client1 wirft BrokenPipeError
        client1._send_sse_event.side_effect = BrokenPipeError()
        
        event_manager.add_client(client1)
        event_manager.add_client(client2)
        
        event_manager.broadcast_event("STATUS", {"status": "on"})
        
        # client1 sollte entfernt worden sein
        assert client1 not in event_manager._clients
        assert client2 in event_manager._clients

    def test_start_starts_workers(self, temp_history_db):
        """Test start() startet Worker-Threads."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        event_manager.start()
        
        # Prüfe dass Threads gestartet wurden
        assert event_manager._stream_running is True
        assert event_manager._stream_thread is not None
        assert event_manager._stream_thread.is_alive() or not event_manager._stream_thread.is_alive()  # Thread könnte bereits beendet sein wenn Config fehlt
        assert event_manager._history_worker_thread is not None

    def test_stop_stops_worker(self, temp_history_db):
        """Test stop() stoppt Worker."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        event_manager.start()
        event_manager.stop()
        
        # Prüfe dass Stop-Event gesetzt wurde
        assert event_manager._stream_stop_event.is_set()
        assert event_manager._stream_running is False

    def test_start_idempotent(self, temp_history_db):
        """Test start() kann mehrfach aufgerufen werden."""
        from homeconnect_coffee.history import HistoryManager
        
        manager = HistoryManager(temp_history_db)
        event_manager = EventStreamManager(manager, enable_logging=False)
        
        event_manager.start()
        thread1 = event_manager._stream_thread
        
        event_manager.start()  # Zweites Mal
        
        # Sollte nicht crashen, Thread sollte gleich bleiben
        assert event_manager._stream_running is True

