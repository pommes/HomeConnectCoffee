"""Unit-Tests für history.py (HistoryManager)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from homeconnect_coffee.history import HistoryManager


@pytest.mark.unit
class TestHistoryManager:
    """Tests für HistoryManager Klasse."""

    def test_init_creates_database(self, temp_history_db: Path):
        """Test dass __init__ die Datenbank erstellt."""
        manager = HistoryManager(temp_history_db)
        
        assert temp_history_db.exists()
        
        # Prüfe dass Schema erstellt wurde
        import sqlite3
        conn = sqlite3.connect(str(temp_history_db))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
            result = cursor.fetchone()
            assert result is not None
        finally:
            conn.close()

    def test_add_event(self, temp_history_db: Path):
        """Test add_event() fügt Event hinzu."""
        manager = HistoryManager(temp_history_db)
        
        event_data = {"key": "value", "number": 42}
        manager.add_event("test_event", event_data)
        
        # Prüfe dass Event gespeichert wurde
        history = manager.get_history()
        assert len(history) == 1
        assert history[0]["type"] == "test_event"
        assert history[0]["data"] == event_data

    def test_add_event_with_timestamp(self, temp_history_db: Path):
        """Test add_event() mit explizitem Timestamp."""
        manager = HistoryManager(temp_history_db)
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        event_data = {"test": "data"}
        manager.add_event("test_event", event_data, timestamp=timestamp)
        
        history = manager.get_history()
        assert len(history) == 1
        assert history[0]["timestamp"] == timestamp.isoformat()

    def test_get_history_empty(self, temp_history_db: Path):
        """Test get_history() mit leerer Datenbank."""
        manager = HistoryManager(temp_history_db)
        
        history = manager.get_history()
        assert history == []

    def test_get_history_filter_by_type(self, temp_history_db: Path):
        """Test get_history() mit Event-Typ-Filter."""
        manager = HistoryManager(temp_history_db)
        
        manager.add_event("type1", {"data": 1})
        manager.add_event("type2", {"data": 2})
        manager.add_event("type1", {"data": 3})
        
        history = manager.get_history(event_type="type1")
        assert len(history) == 2
        assert all(event["type"] == "type1" for event in history)

    def test_get_history_with_limit(self, temp_history_db: Path):
        """Test get_history() mit Limit."""
        manager = HistoryManager(temp_history_db)
        
        # Füge 5 Events hinzu
        for i in range(5):
            manager.add_event("test", {"index": i})
        
        history = manager.get_history(limit=3)
        assert len(history) == 3
        # Sollte die letzten 3 Events sein (chronologisch)
        assert history[0]["data"]["index"] == 2
        assert history[1]["data"]["index"] == 3
        assert history[2]["data"]["index"] == 4

    def test_get_history_with_before_timestamp(self, temp_history_db: Path):
        """Test get_history() mit before_timestamp (Cursor-Pagination)."""
        manager = HistoryManager(temp_history_db)
        
        # Füge Events mit verschiedenen Timestamps hinzu
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            timestamp = base_time + timedelta(hours=i)
            manager.add_event("test", {"index": i}, timestamp=timestamp)
        
        # Hole Events vor dem 3. Event
        cutoff = (base_time + timedelta(hours=2)).isoformat()
        history = manager.get_history(before_timestamp=cutoff, limit=2)
        
        assert len(history) == 2
        # Sollte die 2 Events vor dem Cutoff sein (chronologisch)
        assert history[0]["data"]["index"] == 0
        assert history[1]["data"]["index"] == 1

    def test_get_program_history(self, temp_history_db: Path):
        """Test get_program_history()."""
        manager = HistoryManager(temp_history_db)
        
        manager.add_event("program_started", {"program": "Espresso"})
        manager.add_event("other_event", {"data": "test"})
        manager.add_event("program_started", {"program": "Cappuccino"})
        
        program_history = manager.get_program_history()
        assert len(program_history) == 2
        assert all(event["type"] == "program_started" for event in program_history)

    def test_get_status_changes(self, temp_history_db: Path):
        """Test get_status_changes()."""
        manager = HistoryManager(temp_history_db)
        
        manager.add_event("status_changed", {"status": "on"})
        manager.add_event("other_event", {"data": "test"})
        manager.add_event("status_changed", {"status": "off"})
        
        status_changes = manager.get_status_changes()
        assert len(status_changes) == 2
        assert all(event["type"] == "status_changed" for event in status_changes)

    def test_get_daily_usage(self, temp_history_db: Path):
        """Test get_daily_usage()."""
        manager = HistoryManager(temp_history_db)
        
        # Füge Events für verschiedene Tage hinzu
        today = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
        
        # 2 Events heute
        manager.add_event("program_started", {"program": "Espresso"}, timestamp=today)
        manager.add_event("program_started", {"program": "Cappuccino"}, timestamp=today)
        
        # 1 Event gestern
        yesterday = today - timedelta(days=1)
        manager.add_event("program_started", {"program": "Espresso"}, timestamp=yesterday)
        
        # 1 Event vor 8 Tagen (sollte nicht gezählt werden)
        old_date = today - timedelta(days=8)
        manager.add_event("program_started", {"program": "Espresso"}, timestamp=old_date)
        
        daily_usage = manager.get_daily_usage(days=7)
        
        # Sollte die letzten 7 Tage enthalten
        assert len(daily_usage) == 7
        
        # Heute sollte 2 haben
        today_key = today.strftime("%Y-%m-%d")
        assert daily_usage.get(today_key, 0) == 2
        
        # Gestern sollte 1 haben
        yesterday_key = yesterday.strftime("%Y-%m-%d")
        assert daily_usage.get(yesterday_key, 0) == 1

    def test_get_program_counts(self, temp_history_db: Path):
        """Test get_program_counts()."""
        manager = HistoryManager(temp_history_db)
        
        manager.add_event("program_started", {"program": "Espresso"})
        manager.add_event("program_started", {"program": "Cappuccino"})
        manager.add_event("program_started", {"program": "Espresso"})
        manager.add_event("program_started", {"program": "Espresso"})
        
        counts = manager.get_program_counts()
        
        assert counts["Espresso"] == 3
        assert counts["Cappuccino"] == 1

    def test_thread_safety(self, temp_history_db: Path):
        """Test dass HistoryManager thread-safe ist."""
        import threading
        
        manager = HistoryManager(temp_history_db)
        
        def add_events(start: int, count: int):
            for i in range(start, start + count):
                manager.add_event("test", {"index": i})
        
        # Starte mehrere Threads, die gleichzeitig Events hinzufügen
        threads = []
        for i in range(5):
            thread = threading.Thread(target=add_events, args=(i * 10, 10))
            threads.append(thread)
            thread.start()
        
        # Warte auf alle Threads
        for thread in threads:
            thread.join()
        
        # Prüfe dass alle Events gespeichert wurden
        history = manager.get_history()
        assert len(history) == 50

