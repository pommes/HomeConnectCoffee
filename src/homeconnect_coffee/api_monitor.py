from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock
from typing import Dict, Optional


class APICallMonitor:
    """Überwacht API-Calls zur HomeConnect API und warnt bei hohem Verbrauch."""

    DAILY_LIMIT = 1000  # HomeConnect API Limit: 1000 Calls/Tag
    WARNING_THRESHOLD_80 = 800  # Warnung bei 80%
    WARNING_THRESHOLD_95 = 950  # Warnung bei 95%

    def __init__(self, stats_path: Path) -> None:
        """Initialisiert den API-Call-Monitor.
        
        Args:
            stats_path: Pfad zur JSON-Datei für Statistiken
        """
        self.stats_path = stats_path
        self._lock = Lock()
        self._ensure_stats_file()

    def _ensure_stats_file(self) -> None:
        """Stellt sicher, dass die Stats-Datei existiert."""
        if not self.stats_path.exists():
            self.stats_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_stats({
                "current_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "calls_today": 0,
                "last_reset": datetime.now(timezone.utc).isoformat(),
            })

    def _read_stats(self) -> Dict:
        """Liest die Statistiken aus der Datei."""
        with self._lock:
            try:
                if not self.stats_path.exists():
                    return {
                        "current_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "calls_today": 0,
                        "last_reset": datetime.now(timezone.utc).isoformat(),
                    }
                with open(self.stats_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {
                    "current_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "calls_today": 0,
                    "last_reset": datetime.now(timezone.utc).isoformat(),
                }

    def _write_stats(self, stats: Dict) -> None:
        """Schreibt die Statistiken in die Datei."""
        with self._lock:
            try:
                with open(self.stats_path, "w", encoding="utf-8") as f:
                    json.dump(stats, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"WARNUNG: Fehler beim Schreiben der API-Statistiken: {e}")

    def _reset_if_new_day(self, stats: Dict) -> Dict:
        """Setzt die Statistiken zurück, wenn ein neuer Tag begonnen hat."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        current_day = stats.get("current_day", today)
        
        if current_day != today:
            # Neuer Tag - Statistiken zurücksetzen
            stats = {
                "current_day": today,
                "calls_today": 0,
                "last_reset": datetime.now(timezone.utc).isoformat(),
            }
            self._write_stats(stats)
            print(f"📊 API-Call-Monitor: Neuer Tag - Statistiken zurückgesetzt")
        
        return stats

    def record_call(self, endpoint: str, method: str = "GET") -> None:
        """Zeichnet einen API-Call auf.
        
        Args:
            endpoint: Der API-Endpoint (z.B. "/homeappliances/.../status")
            method: HTTP-Methode (GET, POST, PUT, DELETE)
        """
        stats = self._read_stats()
        stats = self._reset_if_new_day(stats)
        
        stats["calls_today"] = stats.get("calls_today", 0) + 1
        calls_today = stats["calls_today"]
        
        self._write_stats(stats)
        
        # Warnungen ausgeben
        if calls_today >= self.DAILY_LIMIT:
            print(f"⚠️  API-Call-Limit erreicht! ({calls_today}/{self.DAILY_LIMIT} Calls heute)")
            print(f"   Weitere API-Calls werden bis zum nächsten Tag blockiert.")
        elif calls_today >= self.WARNING_THRESHOLD_95:
            remaining = self.DAILY_LIMIT - calls_today
            print(f"⚠️  API-Call-Limit fast erreicht! ({calls_today}/{self.DAILY_LIMIT} Calls heute, {remaining} verbleibend)")
        elif calls_today >= self.WARNING_THRESHOLD_80:
            remaining = self.DAILY_LIMIT - calls_today
            print(f"⚠️  API-Call-Verbrauch hoch: {calls_today}/{self.DAILY_LIMIT} Calls heute ({remaining} verbleibend)")

    def get_stats(self) -> Dict:
        """Gibt die aktuellen Statistiken zurück."""
        stats = self._read_stats()
        stats = self._reset_if_new_day(stats)
        return {
            "calls_today": stats.get("calls_today", 0),
            "limit": self.DAILY_LIMIT,
            "remaining": self.DAILY_LIMIT - stats.get("calls_today", 0),
            "percentage": round((stats.get("calls_today", 0) / self.DAILY_LIMIT) * 100, 1),
            "current_day": stats.get("current_day", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        }

    def print_stats(self) -> None:
        """Gibt die aktuellen Statistiken aus."""
        stats = self.get_stats()
        print(f"📊 API-Call-Statistiken (heute, {stats['current_day']}):")
        print(f"   Verbraucht: {stats['calls_today']}/{stats['limit']} Calls ({stats['percentage']}%)")
        print(f"   Verbleibend: {stats['remaining']} Calls")


# Globaler Monitor-Instanz
_monitor: Optional[APICallMonitor] = None


def get_monitor(stats_path: Optional[Path] = None) -> APICallMonitor:
    """Gibt die globale Monitor-Instanz zurück."""
    global _monitor
    if _monitor is None:
        if stats_path is None:
            # Default: Im Projekt-Root
            stats_path = Path(__file__).parent.parent.parent / "api_stats.json"
        _monitor = APICallMonitor(stats_path)
    return _monitor


def record_api_call(endpoint: str, method: str = "GET") -> None:
    """Zeichnet einen API-Call auf (globale Funktion)."""
    try:
        get_monitor().record_call(endpoint, method)
    except Exception as e:
        # Fehler beim Monitoring sollten API-Calls nicht blockieren
        print(f"WARNUNG: Fehler beim API-Call-Monitoring: {e}")

