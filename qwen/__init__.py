"""Qwen - Financial modeling toolkit for backtesting, options pricing, and paper trading."""

__version__ = "0.1.0"

from qwen.config import Config
from qwen.watchlist import (
    Watchlist,
    WatchlistStock,
    Sector,
    RiskLevel,
    get_watchlist,
    get_ai_plays,
    get_defense_plays,
    get_infrastructure_plays,
    get_nuclear_plays,
    get_evtol_plays,
    get_space_plays,
)

__all__ = [
    "Config",
    "__version__",
    "Watchlist",
    "WatchlistStock",
    "Sector",
    "RiskLevel",
    "get_watchlist",
    "get_ai_plays",
    "get_defense_plays",
    "get_infrastructure_plays",
    "get_nuclear_plays",
    "get_evtol_plays",
    "get_space_plays",
]
