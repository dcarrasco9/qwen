"""Abstract base class for data providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd


@dataclass
class OptionContract:
    """Represents an options contract."""

    symbol: str
    underlying: str
    strike: float
    expiration: datetime
    option_type: str  # 'call' or 'put'
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_volatility: float

    @property
    def mid(self) -> float:
        """Mid price between bid and ask."""
        return (self.bid + self.ask) / 2


@dataclass
class Quote:
    """Current quote for a security."""

    symbol: str
    last: float
    bid: float
    ask: float
    volume: int
    timestamp: datetime

    @property
    def mid(self) -> float:
        """Mid price between bid and ask."""
        return (self.bid + self.ask) / 2


class DataProvider(ABC):
    """Abstract base class for market data providers."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        """Get current quote for a symbol."""
        pass

    @abstractmethod
    def get_historical(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data.

        Args:
            symbol: Ticker symbol
            start: Start date
            end: End date
            interval: Data interval ('1d', '1h', '5m', etc.)

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
        """
        pass

    @abstractmethod
    def get_options_chain(self, symbol: str, expiration: Optional[datetime] = None) -> list[OptionContract]:
        """
        Get options chain for a symbol.

        Args:
            symbol: Underlying ticker symbol
            expiration: Specific expiration date (None for all expirations)

        Returns:
            List of OptionContract objects
        """
        pass

    @abstractmethod
    def get_expirations(self, symbol: str) -> list[datetime]:
        """Get available option expiration dates for a symbol."""
        pass
