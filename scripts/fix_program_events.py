#!/usr/bin/env python3
"""
Fixes missing program_started events in SQLite history database.
Processes existing EVENT/NOTIFY events and creates program_started events if missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from homeconnect_coffee.history import HistoryManager


def fix_program_events(db_path: Path) -> None:
    """Processes existing events and adds missing program_started events."""
    manager = HistoryManager(db_path)
    
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
            manager.add_event(
                new_event["type"],
                new_event["data"],
                timestamp=None  # Will use timestamp from event
            )
        print(f"✓ History updated!")
    else:
        print("No new events found.")


def main() -> None:
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix missing program_started events in SQLite history")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("history.db"),
        help="Path to SQLite history database (default: history.db)"
    )
    args = parser.parse_args()
    
    if not args.db.exists():
        print(f"History database not found: {args.db}")
        sys.exit(1)
    
    print(f"Processing history database: {args.db}")
    fix_program_events(args.db)


if __name__ == "__main__":
    main()

