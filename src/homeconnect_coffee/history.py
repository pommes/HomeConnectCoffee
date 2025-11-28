from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional


class HistoryManager:
    """Verwaltet Verlaufsdaten für das Dashboard mit SQLite."""

    def __init__(self, history_path: Path) -> None:
        """Initialisiert den HistoryManager mit SQLite-Datenbank.
        
        Falls history.json existiert, wird automatisch migriert.
        """
        # Konvertiere .json Pfad zu .db Pfad
        if history_path.suffix == ".json":
            self.db_path = history_path.with_suffix(".db")
            self.json_path = history_path
        else:
            self.db_path = history_path
            self.json_path = history_path.with_suffix(".json")
        
        self._lock = Lock()  # Lock für Thread-sichere Zugriffe
        self._ensure_database()
        
        # Automatische Migration von JSON zu SQLite
        self._migrate_from_json_if_needed()

    def _ensure_database(self) -> None:
        """Stellt sicher, dass die SQLite-Datenbank existiert und das Schema erstellt ist."""
        with self._lock:
            if not self.db_path.exists():
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                # Erstelle Events-Tabelle
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        type TEXT NOT NULL,
                        data TEXT NOT NULL
                    )
                """)
                # Erstelle Indizes für bessere Performance
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
        """Migriert Events von history.json zu history.db, falls JSON existiert und DB leer ist."""
        if not self.json_path.exists():
            return  # Keine JSON-Datei vorhanden
        
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                # Prüfe ob DB bereits Events enthält
                cursor.execute("SELECT COUNT(*) FROM events")
                count = cursor.fetchone()[0]
                
                if count > 0:
                    # DB enthält bereits Events, keine Migration nötig
                    return
                
                # Lade Events aus JSON
                try:
                    with open(self.json_path, "r", encoding="utf-8") as f:
                        json_events = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    return  # JSON ist beschädigt oder nicht lesbar
                
                if not json_events:
                    return  # JSON ist leer
                
                # Importiere Events in SQLite
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
                        print(f"WARNUNG: Fehler beim Importieren eines Events: {e}")
                        continue
                
                conn.commit()
                
                if imported > 0:
                    # Benenne JSON-Datei zu Backup um
                    backup_path = self.json_path.with_suffix(".json.backup")
                    try:
                        self.json_path.rename(backup_path)
                        print(f"✓ {imported} Events von {self.json_path.name} nach {self.db_path.name} migriert")
                        print(f"  Original-JSON gesichert als {backup_path.name}")
                    except Exception as e:
                        print(f"WARNUNG: Konnte JSON nicht zu Backup umbenennen: {e}")
            finally:
                conn.close()

    def add_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Fügt ein Event zur History hinzu."""
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
            # Fehler beim Speichern nicht weiterwerfen, aber loggen
            print(f"WARNUNG: Fehler beim Speichern von Event in History: {e}")

    def get_history(
        self, 
        event_type: Optional[str] = None, 
        limit: Optional[int] = None,
        before_timestamp: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Gibt die History zurück, optional gefiltert nach Event-Typ.
        
        Args:
            event_type: Optionaler Filter für Event-Typ
            limit: Maximale Anzahl Events (wenn gesetzt, werden die letzten N Events zurückgegeben)
            before_timestamp: ISO 8601 Timestamp - gibt nur Events zurück, die vor diesem Zeitpunkt liegen
                            (für Cursor-basierte Pagination)
        
        Returns:
            Liste von Events, chronologisch sortiert (älteste zuerst)
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
                
                # Cursor-basierte Pagination: Events vor before_timestamp, absteigend sortiert
                # Dann umkehren für chronologische Reihenfolge (älteste zuerst)
                if before_timestamp:
                    query += " ORDER BY timestamp DESC"
                    if limit:
                        query += " LIMIT ?"
                        params.append(limit)
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    # Reihenfolge umkehren für chronologische Reihenfolge (älteste zuerst)
                    rows = list(reversed(rows))
                elif limit:
                    # Ohne before_timestamp: Neueste Events zuerst, dann umkehren
                    query += " ORDER BY timestamp DESC LIMIT ?"
                    params.append(limit)
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    # Reihenfolge umkehren für chronologische Reihenfolge (älteste zuerst)
                    rows = list(reversed(rows))
                else:
                    # Alle Events chronologisch
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
        """Gibt die Programm-Historie zurück."""
        return self.get_history("program_started", limit)

    def get_status_changes(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Gibt Status-Änderungen zurück."""
        return self.get_history("status_changed", limit)

    def get_daily_usage(self, days: int = 7) -> Dict[str, int]:
        """Gibt die tägliche Nutzung der letzten N Tage zurück."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                
                # Berechne Cutoff-Datum
                cutoff_date = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) - timedelta(days=days)
                cutoff_str = cutoff_date.isoformat()
                
                # Query für program_started Events mit Datum-Filterung
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
                
                # Erstelle Liste der letzten 'days' Tage
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
                
                # Fülle fehlende Tage mit 0 auf
                full_daily_counts = {
                    date_key: daily_counts.get(date_key, 0) for date_key in date_keys_in_range
                }
                
                return full_daily_counts
            finally:
                conn.close()

    def get_program_counts(self) -> Dict[str, int]:
        """Gibt die Anzahl der Nutzung pro Programm zurück."""
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
