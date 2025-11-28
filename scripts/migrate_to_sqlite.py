#!/usr/bin/env python3
"""Migrates events from history.json to history.db."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

# Adjust PYTHONPATH so homeconnect_coffee can be found
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def migrate_json_to_sqlite(json_path: Path, db_path: Path) -> int:
    """Migrates events from JSON to SQLite.
    
    Returns:
        Number of migrated events
    """
    if not json_path.exists():
        print(f"Error: {json_path} does not exist.")
        return 0
    
    # Load events from JSON
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            json_events = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: JSON file is corrupted: {e}")
        return 0
    except FileNotFoundError:
        print(f"Error: {json_path} not found.")
        return 0
    
    if not json_events:
        print("No events found in JSON file.")
        return 0
    
    # Create SQLite database
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    
    try:
        cursor = conn.cursor()
        
        # Create schema
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
        
        # Check if events already exist
        cursor.execute("SELECT COUNT(*) FROM events")
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            print(f"WARNING: Database already contains {existing_count} events.")
            response = input("Migrate anyway? (y/N): ")
            if response.lower() != "y":
                print("Migration cancelled.")
                return 0
        
        # Import events
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
                print(f"WARNING: Error importing an event: {e}")
                skipped += 1
                continue
        
        conn.commit()
        
        print(f"✓ {imported} events successfully migrated")
        if skipped > 0:
            print(f"  {skipped} events skipped (errors)")
        
        return imported
    finally:
        conn.close()


def main() -> None:
    """Main function for manual migration."""
    project_root = Path(__file__).parent.parent
    json_path = project_root / "history.json"
    db_path = project_root / "history.db"
    
    print(f"Migration from {json_path.name} to {db_path.name}...")
    print()
    
    imported = migrate_json_to_sqlite(json_path, db_path)
    
    if imported > 0:
        print()
        print("Migration completed!")
        print(f"  SQLite database: {db_path}")
        print(f"  Original JSON: {json_path}")
        print()
        print("Tip: You can keep the JSON file as backup or delete it.")


if __name__ == "__main__":
    main()


