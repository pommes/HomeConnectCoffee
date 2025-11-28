from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional


class HistoryManager:
    """Manages history data for the dashboard with SQLite."""

    def __init__(self, history_path: Path) -> None:
        """Initializes the HistoryManager with SQLite database.
        
        If history.json exists, it will be automatically migrated.
        """
        # Convert .json path to .db path
        if history_path.suffix == ".json":
            self.db_path = history_path.with_suffix(".db")
            self.json_path = history_path
        else:
            self.db_path = history_path
            self.json_path = history_path.with_suffix(".json")
        
        self._lock = Lock()  # Lock for thread-safe access
        self._ensure_database()
        
        # Automatic migration from JSON to SQLite
        self._migrate_from_json_if_needed()

    def _ensure_database(self) -> None:
        """Ensures that the SQLite database exists and the schema is created."""
        with self._lock:
            if not self.db_path.exists():
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                # Create events table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        type TEXT NOT NULL,
                        data TEXT NOT NULL
                    )
                """)
                # Create indexes for better performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp ON events(timestamp)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_type ON events(type)
                """)
                conn.commit()
            finally:
                conn.close()

    def _migrate_from_json_if_needed(self) -> None:
        """Migrates events from history.json to history.db if JSON exists and DB is empty."""
        if not self.json_path.exists():
            return  # No JSON file present
        
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                # Check if DB already contains events
                cursor.execute("SELECT COUNT(*) FROM events")
                count = cursor.fetchone()[0]
                
                if count > 0:
                    # DB already contains events, no migration needed
                    return
                
                # Load events from JSON
                try:
                    with open(self.json_path, "r", encoding="utf-8") as f:
                        json_events = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    return  # JSON is corrupted or not readable
                
                if not json_events:
                    return  # JSON is empty
                
                # Import events into SQLite
                imported = 0
                for event in json_events:
                    try:
                        timestamp = event.get("timestamp", "")
                        event_type = event.get("type", "")
                        data_json = json.dumps(event.get("data", {}), ensure_ascii=False)
                        
                        cursor.execute(
                            "INSERT INTO events (timestamp, type, data) VALUES (?, ?, ?)",
                            (timestamp, event_type, data_json)
                        )
                        imported += 1
                    except Exception as e:
                        print(f"WARNING: Error importing event: {e}")
                        continue
                
                conn.commit()
                
                if imported > 0:
                    # Rename JSON file to backup
                    backup_path = self.json_path.with_suffix(".json.backup")
                    try:
                        self.json_path.rename(backup_path)
                        print(f"✓ {imported} events migrated from {self.json_path.name} to {self.db_path.name}")
                        print(f"  Original JSON backed up as {backup_path.name}")
                    except Exception as e:
                        print(f"WARNING: Could not rename JSON to backup: {e}")
            finally:
                conn.close()

    def add_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Adds an event to the history."""
        try:
            if timestamp is None:
                timestamp = datetime.now(timezone.utc)
            
            timestamp_str = timestamp.isoformat()
            data_json = json.dumps(data, ensure_ascii=False)
            
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO events (timestamp, type, data) VALUES (?, ?, ?)",
                        (timestamp_str, event_type, data_json)
                    )
                    conn.commit()
                finally:
                    conn.close()
        except Exception as e:
            # Don't propagate save errors, but log them
            print(f"WARNING: Error saving event to history: {e}")

    def get_history(
        self, 
        event_type: Optional[str] = None, 
        limit: Optional[int] = None,
        before_timestamp: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns the history, optionally filtered by event type.
        
        Args:
            event_type: Optional filter for event type
            limit: Maximum number of events (if set, returns the last N events)
            before_timestamp: ISO 8601 timestamp - only returns events before this time
                            (for cursor-based pagination)
        
        Returns:
            List of events, chronologically sorted (oldest first)
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                
                query = "SELECT timestamp, type, data FROM events"
                params = []
                conditions = []
                
                if event_type:
                    conditions.append("type = ?")
                    params.append(event_type)
                
                if before_timestamp:
                    conditions.append("timestamp < ?")
                    params.append(before_timestamp)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                # Cursor-based pagination: events before before_timestamp, sorted descending
                # Then reverse for chronological order (oldest first)
                if before_timestamp:
                    query += " ORDER BY timestamp DESC"
                    if limit:
                        query += " LIMIT ?"
                        params.append(limit)
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    # Reverse order for chronological order (oldest first)
                    rows = list(reversed(rows))
                elif limit:
                    # Without before_timestamp: newest events first, then reverse
                    query += " ORDER BY timestamp DESC LIMIT ?"
                    params.append(limit)
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    # Reverse order for chronological order (oldest first)
                    rows = list(reversed(rows))
                else:
                    # All events chronologically
                    query += " ORDER BY timestamp ASC"
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                
                events = []
                for row in rows:
                    timestamp, event_type, data_json = row
                    try:
                        data = json.loads(data_json)
                        events.append({
                            "timestamp": timestamp,
                            "type": event_type,
                            "data": data,
                        })
                    except json.JSONDecodeError:
                        continue
                
                return events
            finally:
                conn.close()

    def get_program_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Returns the program history."""
        return self.get_history("program_started", limit)

    def get_status_changes(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Returns status changes."""
        return self.get_history("status_changed", limit)

    def get_daily_usage(self, days: int = 7) -> Dict[str, int]:
        """Returns the daily usage of the last N days."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                
                # Calculate cutoff date
                cutoff_date = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) - timedelta(days=days)
                cutoff_str = cutoff_date.isoformat()
                
                # Query for program_started events with date filtering
                query = """
                    SELECT timestamp, data
                    FROM events
                    WHERE type = 'program_started'
                    AND timestamp >= ?
                    ORDER BY timestamp ASC
                """
                cursor.execute(query, (cutoff_str,))
                rows = cursor.fetchall()
                
                daily_counts: Dict[str, int] = {}
                
                # Create list of last 'days' days
                today = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                date_keys_in_range = [
                    (today - timedelta(days=i)).strftime("%Y-%m-%d")
                    for i in range(days - 1, -1, -1)
                ]
                
                for row in rows:
                    timestamp_str, data_json = row
                    try:
                        event_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        date_key = event_time.strftime("%Y-%m-%d")
                        
                        if date_key in date_keys_in_range:
                            daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
                    except (KeyError, ValueError):
                        continue
                
                # Fill missing days with 0
                full_daily_counts = {
                    date_key: daily_counts.get(date_key, 0) for date_key in date_keys_in_range
                }
                
                return full_daily_counts
            finally:
                conn.close()

    def get_program_counts(self) -> Dict[str, int]:
        """Returns the usage count per program."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                
                query = """
                    SELECT data
                    FROM events
                    WHERE type = 'program_started'
                """
                cursor.execute(query)
                rows = cursor.fetchall()
                
                counts: Dict[str, int] = {}
                
                for row in rows:
                    data_json, = row
                    try:
                        data = json.loads(data_json)
                        program_key = data.get("program", "Unknown")
                        counts[program_key] = counts.get(program_key, 0) + 1
                    except (json.JSONDecodeError, KeyError):
                        continue
                
                return counts
            finally:
                conn.close()
