from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional


class HistoryManager:
    """Verwaltet Verlaufsdaten für das Dashboard."""

    def __init__(self, history_path: Path) -> None:
        self.history_path = history_path
        self._lock = Lock()  # Lock für Thread-sichere Zugriffe
        self._ensure_history_file()

    def _ensure_history_file(self) -> None:
        """Stellt sicher, dass die History-Datei existiert."""
        if not self.history_path.exists():
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_history([])
        # Datei existiert bereits - nicht überschreiben!

    def _read_history(self) -> List[Dict[str, Any]]:
        """Liest die History-Datei."""
        with self._lock:
            try:
                if not self.history_path.exists():
                    return []
                with open(self.history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []

    def _write_history(self, history: List[Dict[str, Any]]) -> None:
        """Schreibt die History-Datei atomar (um Datenverlust zu vermeiden)."""
        with self._lock:
            # Atomares Schreiben: Zuerst in temporäre Datei, dann umbenennen
            temp_path = self.history_path.with_suffix(".tmp")
            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(history, f, indent=2, ensure_ascii=False)
                # Atomar umbenennen (auf den meisten Systemen)
                temp_path.replace(self.history_path)
            except Exception as e:
                # Bei Fehler temporäre Datei löschen
                if temp_path.exists():
                    temp_path.unlink()
                raise RuntimeError(f"Fehler beim Schreiben der History: {e}") from e

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

            event = {
                "timestamp": timestamp.isoformat(),
                "type": event_type,
                "data": data,
            }

            history = self._read_history()
            history.append(event)

            # Begrenze auf letzte 1000 Events (optional, kann angepasst werden)
            if len(history) > 1000:
                history = history[-1000:]

            self._write_history(history)
        except Exception as e:
            # Fehler beim Speichern nicht weiterwerfen, aber loggen
            print(f"WARNUNG: Fehler beim Speichern von Event in History: {e}")
            # Versuche zumindest die Datei zu retten, falls sie beschädigt ist
            try:
                if not self.history_path.exists() or self.history_path.stat().st_size == 0:
                    # Datei existiert nicht oder ist leer - erstelle neue
                    self._write_history([])
            except Exception:
                pass

    def get_history(
        self, event_type: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Gibt die History zurück, optional gefiltert nach Event-Typ."""
        history = self._read_history()

        if event_type:
            history = [e for e in history if e.get("type") == event_type]

        if limit:
            history = history[-limit:]

        return history

    def get_program_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Gibt die Programm-Historie zurück."""
        return self.get_history("program_started", limit)

    def get_status_changes(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Gibt Status-Änderungen zurück."""
        return self.get_history("status_changed", limit)

    def get_daily_usage(self, days: int = 7) -> Dict[str, int]:
        """Gibt die tägliche Nutzung der letzten N Tage zurück."""
        from datetime import timedelta
        
        history = self._read_history()
        program_events = [e for e in history if e.get("type") == "program_started"]

        daily_counts: Dict[str, int] = {}

        # Berechne Cutoff-Datum korrekt mit timedelta
        cutoff_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=days)

        for event in program_events:
            try:
                event_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                if event_time < cutoff_date:
                    continue

                date_key = event_time.strftime("%Y-%m-%d")
                daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
            except (KeyError, ValueError):
                continue

        return daily_counts

    def get_program_counts(self) -> Dict[str, int]:
        """Gibt die Anzahl der Nutzung pro Programm zurück."""
        history = self._read_history()
        program_events = [e for e in history if e.get("type") == "program_started"]

        counts: Dict[str, int] = {}

        for event in program_events:
            program_key = event.get("data", {}).get("program", "Unknown")
            counts[program_key] = counts.get(program_key, 0) + 1

        return counts

