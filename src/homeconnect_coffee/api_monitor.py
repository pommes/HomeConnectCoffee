from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from homeconnect_coffee.history import HistoryManager


class APICallMonitor:
    """Monitors API calls to the HomeConnect API and warns on high usage."""

    DAILY_LIMIT = 1000  # HomeConnect API limit: 1000 calls/day
    WARNING_THRESHOLD_80 = 800  # Warning at 80%
    WARNING_THRESHOLD_95 = 950  # Warning at 95%
    TOKEN_REFRESH_LIMIT = 100  # HomeConnect API limit: 100 token refreshes/day
    TOKEN_REFRESH_WARNING_THRESHOLD = 50  # Warning at 50 refreshes

    def __init__(self, history_manager: HistoryManager, json_stats_path: Optional[Path] = None) -> None:
        """Initializes the API call monitor.
        
        Args:
            history_manager: HistoryManager instance for SQLite access
            json_stats_path: Optional path to old JSON file for migration
        """
        self.history_manager = history_manager
        self._last_day: Optional[str] = None
        
        # Migrate from JSON if it exists (errors should not prevent initialization)
        if json_stats_path and json_stats_path.exists():
            try:
                self.history_manager.migrate_api_stats_from_json(json_stats_path)
            except Exception as e:
                # Migration errors should not prevent monitor from working
                print(f"WARNING: Failed to migrate API statistics from JSON: {e}")

    def _get_today(self) -> str:
        """Returns today's date as YYYY-MM-DD string."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def record_call(self, endpoint: str, method: str = "GET") -> None:
        """Records an API call.
        
        Args:
            endpoint: The API endpoint (e.g., "/homeappliances/.../status")
            method: HTTP method (GET, POST, PUT, DELETE)
        """
        today = self._get_today()
        
        # Check if new day and reset if needed
        if self._last_day and self._last_day != today:
            print(f"📊 API call monitor: New day - statistics reset")
        
        self._last_day = today
        
        # Increment counter
        calls_today = self.history_manager.increment_api_call(today)
        
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
        today = self._get_today()
        
        # Check if new day and reset if needed
        if self._last_day and self._last_day != today:
            print(f"📊 API call monitor: New day - statistics reset")
        
        self._last_day = today
        
        # Increment counter
        refreshes_today = self.history_manager.increment_token_refresh(today)
        
        # Output warnings
        if refreshes_today >= self.TOKEN_REFRESH_LIMIT:
            print(f"⚠️  Token refresh limit reached! ({refreshes_today}/{self.TOKEN_REFRESH_LIMIT} refreshes today)")
            print(f"   Further token refreshes will be blocked until the next day.")
        elif refreshes_today >= self.TOKEN_REFRESH_WARNING_THRESHOLD:
            remaining = self.TOKEN_REFRESH_LIMIT - refreshes_today
            print(f"⚠️  High token refresh usage: {refreshes_today}/{self.TOKEN_REFRESH_LIMIT} refreshes today ({remaining} remaining)")

    def get_stats(self) -> Dict:
        """Returns the current statistics."""
        today = self._get_today()
        stats = self.history_manager.get_api_statistics(today)
        
        calls_today = stats.get("calls_count", 0)
        refreshes_today = stats.get("token_refreshes_count", 0)
        
        return {
            "calls_today": calls_today,
            "limit": self.DAILY_LIMIT,
            "remaining": self.DAILY_LIMIT - calls_today,
            "percentage": round((calls_today / self.DAILY_LIMIT) * 100, 1),
            "current_day": today,
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


def get_monitor(history_manager: Optional[HistoryManager] = None, json_stats_path: Optional[Path] = None) -> APICallMonitor:
    """Returns the global monitor instance.
    
    Args:
        history_manager: HistoryManager instance for SQLite access. If None, creates a default one.
        json_stats_path: Optional path to old JSON file for migration
    
    Note:
        If history_manager is provided and _monitor already exists with a different HistoryManager,
        the existing monitor will be reused. To ensure the correct HistoryManager is used,
        call get_monitor() with history_manager before any other code calls get_monitor().
    """
    global _monitor
    if _monitor is None:
        if history_manager is None:
            # Default: Use history.db in project root
            history_path = Path(__file__).parent.parent.parent / "history.db"
            history_manager = HistoryManager(history_path)
        if json_stats_path is None:
            # Default: Check for api_stats.json in project root
            json_stats_path = Path(__file__).parent.parent.parent / "api_stats.json"
        try:
            _monitor = APICallMonitor(history_manager, json_stats_path)
        except Exception as e:
            # If initialization fails, try without migration
            print(f"WARNING: Failed to initialize API monitor with migration: {e}")
            try:
                _monitor = APICallMonitor(history_manager, None)
            except Exception as e2:
                print(f"ERROR: Failed to initialize API monitor: {e2}")
                raise
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

