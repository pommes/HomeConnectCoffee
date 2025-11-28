#!/usr/bin/env python3
"""Exportiert Events von history.db zu history.json."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

# PYTHONPATH anpassen, damit homeconnect_coffee gefunden wird
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def export_sqlite_to_json(db_path: Path, json_path: Path) -> int:
    """Exportiert Events von SQLite zu JSON.
    
    Returns:
        Anzahl der exportierten Events
    """
    if not db_path.exists():
        print(f"Fehler: {db_path} existiert nicht.")
        return 0
    
    # Verbinde mit SQLite-Datenbank
    conn = sqlite3.connect(str(db_path))
    
    try:
        cursor = conn.cursor()
        
        # Lade alle Events
        cursor.execute("""
            SELECT timestamp, type, data
            FROM events
            ORDER BY timestamp ASC
        """)
        rows = cursor.fetchall()
        
        if not rows:
            print("Keine Events in Datenbank gefunden.")
            return 0
        
        # Konvertiere zu JSON-Format
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
                print(f"WARNUNG: Fehler beim Parsen eines Events: {e}")
                continue
        
        # Schreibe JSON-Datei
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        
        print(f"✓ {len(events)} Events erfolgreich exportiert")
        return len(events)
    finally:
        conn.close()


def main() -> None:
    """Hauptfunktion für manuellen Export."""
    project_root = Path(__file__).parent.parent
    db_path = project_root / "history.db"
    json_path = project_root / "history.json"
    
    print(f"Export von {db_path.name} nach {json_path.name}...")
    print()
    
    if json_path.exists():
        response = input(f"{json_path.name} existiert bereits. Überschreiben? (j/N): ")
        if response.lower() != "j":
            print("Export abgebrochen.")
            return
    
    exported = export_sqlite_to_json(db_path, json_path)
    
    if exported > 0:
        print()
        print("Export abgeschlossen!")
        print(f"  JSON-Datei: {json_path}")
        print(f"  Anzahl Events: {exported}")


if __name__ == "__main__":
    main()


