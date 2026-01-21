"""
DEPRECATED: This module has been moved to qwen.data.watchlist

This shim provides backward compatibility. Please update your imports to:
    from qwen.data.watchlist import Watchlist, WatchlistStock, Sector, RiskLevel
"""

import warnings

warnings.warn(
    "qwen.watchlist is deprecated. Use qwen.data.watchlist instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new location for backward compatibility
from qwen.data.watchlist import (
    Sector,
    RiskLevel,
    WatchlistStock,
    Watchlist,
    WATCHLIST_2026,
    get_watchlist,
    get_ai_plays,
    get_defense_plays,
    get_infrastructure_plays,
    get_nuclear_plays,
    get_evtol_plays,
    get_space_plays,
)

__all__ = [
    "Sector",
    "RiskLevel",
    "WatchlistStock",
    "Watchlist",
    "WATCHLIST_2026",
    "get_watchlist",
    "get_ai_plays",
    "get_defense_plays",
    "get_infrastructure_plays",
    "get_nuclear_plays",
    "get_evtol_plays",
    "get_space_plays",
]
