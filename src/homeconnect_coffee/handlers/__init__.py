"""HTTP handlers for HomeConnect Coffee Server."""

from .base_handler import BaseHandler
from .coffee_handler import CoffeeHandler
from .dashboard_handler import DashboardHandler
from .history_handler import HistoryHandler
from .router import RequestRouter
from .status_handler import StatusHandler

__all__ = [
    "BaseHandler",
    "CoffeeHandler",
    "DashboardHandler",
    "HistoryHandler",
    "RequestRouter",
    "StatusHandler",
]

