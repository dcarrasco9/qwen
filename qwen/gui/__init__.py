"""Qwen GUI components.

Provides a PySide6-based desktop application for monitoring watchlist stocks,
viewing Alpaca account positions, and tracking market data.

Usage:
    python -m qwen.gui.watchlist_monitor

Keyboard Shortcuts:
    Ctrl+R - Refresh prices
    Ctrl+N - Add new stock
    Ctrl+F - Focus search
    Ctrl+1/2/3 - Switch tabs
"""

from .watchlist_monitor import WatchlistMonitor, run_monitor
from .theme import theme, COLORS, COLORS_LIGHT, COLORS_DARK, Dimensions

# Sub-modules
from . import widgets
from . import pages
from . import dialogs
from . import workers

__all__ = [
    "WatchlistMonitor",
    "run_monitor",
    "theme",
    "COLORS",
    "COLORS_LIGHT",
    "COLORS_DARK",
    "Dimensions",
    "widgets",
    "pages",
    "dialogs",
    "workers",
]
