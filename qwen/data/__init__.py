"""Data providers for market data."""

from qwen.data.base import DataProvider
from qwen.data.yahoo import YahooDataProvider
from qwen.data.factory import create_data_provider, get_available_providers, get_default_provider
from qwen.data.watchlist import (
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
    "DataProvider",
    "YahooDataProvider",
    "create_data_provider",
    "get_available_providers",
    "get_default_provider",
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

# Optional Alpaca import
try:
    from qwen.data.alpaca import AlpacaDataProvider
    __all__.append("AlpacaDataProvider")
except ImportError:
    pass
