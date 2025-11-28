#!/usr/bin/env python3
"""Migriert Events von history.json zu history.db."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

# PYTHONPATH anpassen, damit homeconnect_coffee gefunden wird
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def migrate_json_to_sqlite(json_path: Path, db_path: Path) -> int:
    """Migriert Events von JSON zu SQLite.
    
    Returns:
        Anzahl der migrierten Events
    """
    if not json_path.exists():
        print(f"Fehler: {json_path} existiert nicht.")
        return 0
    
    # Lade Events aus JSON
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            json_events = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Fehler: JSON-Datei ist beschädigt: {e}")
        return 0
    except FileNotFoundError:
        print(f"Fehler: {json_path} nicht gefunden.")
        return 0
    
    if not json_events:
        print("Keine Events in JSON-Datei gefunden.")
        return 0
    
    # Erstelle SQLite-Datenbank
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    
    try:
        cursor = conn.cursor()
        
        # Erstelle Schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                data TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON events(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_type ON events(type)
        """)
        
        # Prüfe ob bereits Events vorhanden sind
        cursor.execute("SELECT COUNT(*) FROM events")
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            print(f"WARNUNG: Datenbank enthält bereits {existing_count} Events.")
            response = input("Trotzdem migrieren? (j/N): ")
            if response.lower() != "j":
                print("Migration abgebrochen.")
                return 0
        
        # Importiere Events
        imported = 0
        skipped = 0
        
        for event in json_events:
            try:
                timestamp = event.get("timestamp", "")
                event_type = event.get("type", "")
                data = event.get("data", {})
                data_json = json.dumps(data, ensure_ascii=False)
                
                cursor.execute(
                    "INSERT INTO events (timestamp, type, data) VALUES (?, ?, ?)",
                    (timestamp, event_type, data_json)
                )
                imported += 1
            except Exception as e:
                print(f"WARNUNG: Fehler beim Importieren eines Events: {e}")
                skipped += 1
                continue
        
        conn.commit()
        
        print(f"✓ {imported} Events erfolgreich migriert")
        if skipped > 0:
            print(f"  {skipped} Events übersprungen (Fehler)")
        
        return imported
    finally:
        conn.close()


def main() -> None:
    """Hauptfunktion für manuelle Migration."""
    project_root = Path(__file__).parent.parent
    json_path = project_root / "history.json"
    db_path = project_root / "history.db"
    
    print(f"Migration von {json_path.name} nach {db_path.name}...")
    print()
    
    imported = migrate_json_to_sqlite(json_path, db_path)
    
    if imported > 0:
        print()
        print("Migration abgeschlossen!")
        print(f"  SQLite-Datenbank: {db_path}")
        print(f"  Original-JSON: {json_path}")
        print()
        print("Tipp: Du kannst die JSON-Datei als Backup behalten oder löschen.")


if __name__ == "__main__":
    main()


