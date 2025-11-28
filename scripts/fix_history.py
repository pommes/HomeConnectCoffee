#!/usr/bin/env python3
"""
Processes existing events in the history retroactively and adds missing program_started events.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from homeconnect_coffee.history import HistoryManager


def fix_history(history_path: Path) -> None:
    """Processes existing events and adds missing program_started events."""
    manager = HistoryManager(history_path)
    
    # Read all events
    all_events = manager.get_history()
    
    # Find all events that contain ActiveProgram but don't have a program_started event yet
    program_started_timestamps = {
        event["timestamp"] 
        for event in all_events 
        if event.get("type") == "program_started"
    }
    
    new_events = []
    
    # Search all events for ActiveProgram events
    for event in all_events:
        event_type = event.get("type", "").lower()
        payload = event.get("data", {})
        
        # Check NOTIFY and EVENT events
        if event_type in ("notify", "event"):
            items = payload.get("items", [])
            for item in items:
                item_key = item.get("key")
                item_value = item.get("value")
                
                # ActiveProgram Event: If value is not null, a program was started
                if item_key == "BSH.Common.Root.ActiveProgram" and item_value:
                    # Check if a program_started event already exists for this timestamp
                    event_timestamp = event.get("timestamp")
                    if event_timestamp not in program_started_timestamps:
                        # Add program_started event
                        if isinstance(item_value, dict):
                            # value is an object with "key" and "options"
                            program_key = item_value.get("key", "Unknown")
                            options = item_value.get("options", [])
                        elif isinstance(item_value, str):
                            # value is directly the program key (string)
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
                        print(f"✓ Adding program_started event: {program_key} at {event_timestamp}")
    
    # Add new events to history
    if new_events:
        print(f"\nAdding {len(new_events)} new program_started events...")
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
        print(f"✓ History updated!")
    else:
        print("No new events found.")


def main() -> None:
    history_path = Path(__file__).parent.parent / "history.json"
    
    if not history_path.exists():
        print(f"History file not found: {history_path}")
        sys.exit(1)
    
    print(f"Processing history file: {history_path}")
    fix_history(history_path)


if __name__ == "__main__":
    main()

