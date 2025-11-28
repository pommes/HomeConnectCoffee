#!/usr/bin/env python3
"""
Verarbeitet vorhandene Events in der History nachträglich und fügt fehlende program_started Events hinzu.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Füge src zum Python-Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from homeconnect_coffee.history import HistoryManager


def fix_history(history_path: Path) -> None:
    """Verarbeitet vorhandene Events und fügt fehlende program_started Events hinzu."""
    manager = HistoryManager(history_path)
    
    # Lese alle Events
    all_events = manager.get_history()
    
    # Finde alle Events, die ActiveProgram enthalten, aber noch kein program_started Event haben
    program_started_timestamps = {
        event["timestamp"] 
        for event in all_events 
        if event.get("type") == "program_started"
    }
    
    new_events = []
    
    # Durchsuche alle Events nach ActiveProgram Events
    for event in all_events:
        event_type = event.get("type", "").lower()
        payload = event.get("data", {})
        
        # Prüfe NOTIFY und EVENT Events
        if event_type in ("notify", "event"):
            items = payload.get("items", [])
            for item in items:
                item_key = item.get("key")
                item_value = item.get("value")
                
                # ActiveProgram Event: Wenn value nicht null ist, wurde ein Programm gestartet
                if item_key == "BSH.Common.Root.ActiveProgram" and item_value:
                    # Prüfe ob bereits ein program_started Event für diesen Timestamp existiert
                    event_timestamp = event.get("timestamp")
                    if event_timestamp not in program_started_timestamps:
                        # Füge program_started Event hinzu
                        if isinstance(item_value, dict):
                            # value ist ein Objekt mit "key" und "options"
                            program_key = item_value.get("key", "Unknown")
                            options = item_value.get("options", [])
                        elif isinstance(item_value, str):
                            # value ist direkt der Programm-Key (String)
                            program_key = item_value
                            options = []
                        else:
                            continue
                        
                        new_events.append({
                            "timestamp": event_timestamp,
                            "type": "program_started",
                            "data": {
                                "program": program_key,
                                "options": options,
                            },
                        })
                        program_started_timestamps.add(event_timestamp)
                        print(f"✓ Füge program_started Event hinzu: {program_key} am {event_timestamp}")
    
    # Füge neue Events zur History hinzu
    if new_events:
        print(f"\nFüge {len(new_events)} neue program_started Events hinzu...")
        for new_event in new_events:
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(new_event["timestamp"].replace("Z", "+00:00"))
            except (ValueError, KeyError):
                timestamp = datetime.now(timezone.utc)
            
            manager.add_event(
                new_event["type"],
                new_event["data"],
                timestamp=timestamp
            )
        print(f"✓ History aktualisiert!")
    else:
        print("Keine neuen Events gefunden.")


def main() -> None:
    history_path = Path(__file__).parent.parent / "history.json"
    
    if not history_path.exists():
        print(f"History-Datei nicht gefunden: {history_path}")
        sys.exit(1)
    
    print(f"Verarbeite History-Datei: {history_path}")
    fix_history(history_path)


if __name__ == "__main__":
    main()

