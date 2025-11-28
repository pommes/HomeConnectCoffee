#!/usr/bin/env python3
"""Exports events from history.db to history.json."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

# Adjust PYTHONPATH so homeconnect_coffee can be found
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def export_sqlite_to_json(db_path: Path, json_path: Path) -> int:
    """Exports events from SQLite to JSON.
    
    Returns:
        Number of exported events
    """
    if not db_path.exists():
        print(f"Error: {db_path} does not exist.")
        return 0
    
    # Connect to SQLite database
    conn = sqlite3.connect(str(db_path))
    
    try:
        cursor = conn.cursor()
        
        # Load all events
        cursor.execute("""
            SELECT timestamp, type, data
            FROM events
            ORDER BY timestamp ASC
        """)
        rows = cursor.fetchall()
        
        if not rows:
            print("No events found in database.")
            return 0
        
        # Convert to JSON format
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
            except json.JSONDecodeError as e:
                print(f"WARNING: Error parsing an event: {e}")
                continue
        
        # Write JSON file
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        
        print(f"✓ {len(events)} events successfully exported")
        return len(events)
    finally:
        conn.close()


def main() -> None:
    """Main function for manual export."""
    project_root = Path(__file__).parent.parent
    db_path = project_root / "history.db"
    json_path = project_root / "history.json"
    
    print(f"Export from {db_path.name} to {json_path.name}...")
    print()
    
    if json_path.exists():
        response = input(f"{json_path.name} already exists. Overwrite? (y/N): ")
        if response.lower() != "y":
            print("Export cancelled.")
            return
    
    exported = export_sqlite_to_json(db_path, json_path)
    
    if exported > 0:
        print()
        print("Export completed!")
        print(f"  JSON file: {json_path}")
        print(f"  Number of events: {exported}")


if __name__ == "__main__":
    main()


