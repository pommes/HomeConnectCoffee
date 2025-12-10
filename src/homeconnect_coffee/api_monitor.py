from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock
from typing import Dict, Optional


class APICallMonitor:
    """Monitors API calls to the HomeConnect API and warns on high usage."""

    DAILY_LIMIT = 1000  # HomeConnect API limit: 1000 calls/day
    WARNING_THRESHOLD_80 = 800  # Warning at 80%
    WARNING_THRESHOLD_95 = 950  # Warning at 95%
    TOKEN_REFRESH_LIMIT = 100  # HomeConnect API limit: 100 token refreshes/day
    TOKEN_REFRESH_WARNING_THRESHOLD = 50  # Warning at 50 refreshes

    def __init__(self, stats_path: Path) -> None:
        """Initializes the API call monitor.
        
        Args:
            stats_path: Path to JSON file for statistics
        """
        self.stats_path = stats_path
        self._lock = Lock()
        self._ensure_stats_file()

    def _ensure_stats_file(self) -> None:
        """Ensures that the stats file exists."""
        if not self.stats_path.exists():
            self.stats_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_stats({
                "current_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "calls_today": 0,
                "token_refreshes_today": 0,
                "last_reset": datetime.now(timezone.utc).isoformat(),
            })

    def _read_stats(self) -> Dict:
        """Reads statistics from the file."""
        with self._lock:
            try:
                if not self.stats_path.exists():
                    return {
                        "current_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "calls_today": 0,
                        "token_refreshes_today": 0,
                        "last_reset": datetime.now(timezone.utc).isoformat(),
                    }
                with open(self.stats_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {
                    "current_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "calls_today": 0,
                    "token_refreshes_today": 0,
                    "last_reset": datetime.now(timezone.utc).isoformat(),
                }

    def _write_stats(self, stats: Dict) -> None:
        """Writes statistics to the file."""
        with self._lock:
            try:
                with open(self.stats_path, "w", encoding="utf-8") as f:
                    json.dump(stats, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"WARNING: Error writing API statistics: {e}")

    def _reset_if_new_day(self, stats: Dict) -> Dict:
        """Resets statistics if a new day has started."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        current_day = stats.get("current_day", today)
        
        if current_day != today:
            # New day - reset statistics
            stats = {
                "current_day": today,
                "calls_today": 0,
                "token_refreshes_today": 0,
                "last_reset": datetime.now(timezone.utc).isoformat(),
            }
            self._write_stats(stats)
            print(f"📊 API call monitor: New day - statistics reset")
        
        return stats

    def record_call(self, endpoint: str, method: str = "GET") -> None:
        """Records an API call.
        
        Args:
            endpoint: The API endpoint (e.g., "/homeappliances/.../status")
            method: HTTP method (GET, POST, PUT, DELETE)
        """
        stats = self._read_stats()
        stats = self._reset_if_new_day(stats)
        
        stats["calls_today"] = stats.get("calls_today", 0) + 1
        calls_today = stats["calls_today"]
        
        self._write_stats(stats)
        
        # Output warnings
        if calls_today >= self.DAILY_LIMIT:
            print(f"⚠️  API call limit reached! ({calls_today}/{self.DAILY_LIMIT} calls today)")
            print(f"   Further API calls will be blocked until the next day.")
        elif calls_today >= self.WARNING_THRESHOLD_95:
            remaining = self.DAILY_LIMIT - calls_today
            print(f"⚠️  API call limit almost reached! ({calls_today}/{self.DAILY_LIMIT} calls today, {remaining} remaining)")
        elif calls_today >= self.WARNING_THRESHOLD_80:
            remaining = self.DAILY_LIMIT - calls_today
            print(f"⚠️  High API call usage: {calls_today}/{self.DAILY_LIMIT} calls today ({remaining} remaining)")

    def record_token_refresh(self) -> None:
        """Records a token refresh operation.
        
        This tracks token refreshes separately from regular API calls,
        as they have their own rate limit (100 refreshes/day).
        """
        stats = self._read_stats()
        stats = self._reset_if_new_day(stats)
        
        stats["token_refreshes_today"] = stats.get("token_refreshes_today", 0) + 1
        refreshes_today = stats["token_refreshes_today"]
        
        self._write_stats(stats)
        
        # Output warnings
        if refreshes_today >= self.TOKEN_REFRESH_LIMIT:
            print(f"⚠️  Token refresh limit reached! ({refreshes_today}/{self.TOKEN_REFRESH_LIMIT} refreshes today)")
            print(f"   Further token refreshes will be blocked until the next day.")
        elif refreshes_today >= self.TOKEN_REFRESH_WARNING_THRESHOLD:
            remaining = self.TOKEN_REFRESH_LIMIT - refreshes_today
            print(f"⚠️  High token refresh usage: {refreshes_today}/{self.TOKEN_REFRESH_LIMIT} refreshes today ({remaining} remaining)")

    def get_stats(self) -> Dict:
        """Returns the current statistics."""
        stats = self._read_stats()
        stats = self._reset_if_new_day(stats)
        calls_today = stats.get("calls_today", 0)
        refreshes_today = stats.get("token_refreshes_today", 0)
        return {
            "calls_today": calls_today,
            "limit": self.DAILY_LIMIT,
            "remaining": self.DAILY_LIMIT - calls_today,
            "percentage": round((calls_today / self.DAILY_LIMIT) * 100, 1),
            "current_day": stats.get("current_day", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "token_refreshes_today": refreshes_today,
            "token_refresh_limit": self.TOKEN_REFRESH_LIMIT,
            "token_refresh_remaining": self.TOKEN_REFRESH_LIMIT - refreshes_today,
            "token_refresh_percentage": round((refreshes_today / self.TOKEN_REFRESH_LIMIT) * 100, 1),
        }

    def print_stats(self) -> None:
        """Prints the current statistics."""
        stats = self.get_stats()
        print(f"📊 API call statistics (today, {stats['current_day']}):")
        print(f"   Used: {stats['calls_today']}/{stats['limit']} calls ({stats['percentage']}%)")
        print(f"   Remaining: {stats['remaining']} calls")
        print(f"   Token refreshes: {stats['token_refreshes_today']}/{stats['token_refresh_limit']} ({stats['token_refresh_percentage']}%)")
        print(f"   Token refresh remaining: {stats['token_refresh_remaining']} refreshes")


# Global monitor instance
_monitor: Optional[APICallMonitor] = None


def get_monitor(stats_path: Optional[Path] = None) -> APICallMonitor:
    """Returns the global monitor instance."""
    global _monitor
    if _monitor is None:
        if stats_path is None:
            # Default: In project root
            stats_path = Path(__file__).parent.parent.parent / "api_stats.json"
        _monitor = APICallMonitor(stats_path)
    return _monitor


def record_api_call(endpoint: str, method: str = "GET") -> None:
    """Records an API call (global function)."""
    try:
        get_monitor().record_call(endpoint, method)
    except Exception as e:
        # Monitoring errors should not block API calls
        print(f"WARNING: Error in API call monitoring: {e}")


def record_token_refresh() -> None:
    """Records a token refresh (global function)."""
    try:
        get_monitor().record_token_refresh()
    except Exception as e:
        # Monitoring errors should not block token refreshes
        print(f"WARNING: Error in token refresh monitoring: {e}")

