"""Alpaca Markets data provider."""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from qwen.data.base import DataProvider, OptionContract, Quote
from qwen.config import config

try:
    from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
    from alpaca.data.requests import (
        StockLatestQuoteRequest,
        StockBarsRequest,
        CryptoLatestQuoteRequest,
        CryptoBarsRequest,
    )
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    ALPACA_DATA_AVAILABLE = True
except ImportError:
    ALPACA_DATA_AVAILABLE = False


class AlpacaDataProvider(DataProvider):
    """
    Alpaca Markets data provider.

    Provides real-time and historical data for stocks and crypto.

    Note: Alpaca provides free data with API keys, but some data
    (like real-time quotes) may require a data subscription.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        """
        Initialize Alpaca data provider.

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
        """
        if not ALPACA_DATA_AVAILABLE:
            raise ImportError(
                "alpaca-py is not installed. Install with: pip install alpaca-py"
            )

        self.api_key = api_key or config.alpaca_api_key
        self.secret_key = secret_key or config.alpaca_secret_key

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Alpaca credentials required. Set ALPACA_API_KEY and ALPACA_SECRET_KEY."
            )

        # Initialize data clients
        self._stock_client = StockHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
        )
        self._crypto_client = CryptoHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
        )

    def _is_crypto(self, symbol: str) -> bool:
        """Check if symbol is a crypto pair."""
        return "/" in symbol or symbol.endswith("USD") and len(symbol) <= 7

    def get_quote(self, symbol: str) -> Quote:
        """Get current quote for a symbol."""
        if self._is_crypto(symbol):
            return self._get_crypto_quote(symbol)
        return self._get_stock_quote(symbol)

    def _get_stock_quote(self, symbol: str) -> Quote:
        """Get stock quote."""
        request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quotes = self._stock_client.get_stock_latest_quote(request)

        quote_data = quotes[symbol]
        return Quote(
            symbol=symbol,
            last=float(quote_data.ask_price + quote_data.bid_price) / 2,  # Mid price
            bid=float(quote_data.bid_price),
            ask=float(quote_data.ask_price),
            volume=0,  # Quote doesn't include volume
            timestamp=quote_data.timestamp,
        )

    def _get_crypto_quote(self, symbol: str) -> Quote:
        """Get crypto quote."""
        # Normalize symbol format
        if "/" not in symbol:
            symbol = f"{symbol[:3]}/{symbol[3:]}" if len(symbol) == 6 else f"{symbol}/USD"

        request = CryptoLatestQuoteRequest(symbol_or_symbols=symbol)
        quotes = self._crypto_client.get_crypto_latest_quote(request)

        quote_data = quotes[symbol]
        return Quote(
            symbol=symbol,
            last=float(quote_data.ask_price + quote_data.bid_price) / 2,
            bid=float(quote_data.bid_price),
            ask=float(quote_data.ask_price),
            volume=0,
            timestamp=quote_data.timestamp,
        )

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
            start: Start date (default: 1 year ago)
            end: End date (default: now)
            interval: Data interval ('1m', '5m', '15m', '1h', '1d')

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
        """
        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=365)

        # Map interval to Alpaca TimeFrame
        timeframe_map = {
            "1m": TimeFrame(1, TimeFrameUnit.Minute),
            "5m": TimeFrame(5, TimeFrameUnit.Minute),
            "15m": TimeFrame(15, TimeFrameUnit.Minute),
            "30m": TimeFrame(30, TimeFrameUnit.Minute),
            "1h": TimeFrame(1, TimeFrameUnit.Hour),
            "1d": TimeFrame(1, TimeFrameUnit.Day),
            "1w": TimeFrame(1, TimeFrameUnit.Week),
        }
        timeframe = timeframe_map.get(interval, TimeFrame(1, TimeFrameUnit.Day))

        if self._is_crypto(symbol):
            return self._get_crypto_bars(symbol, start, end, timeframe)
        return self._get_stock_bars(symbol, start, end, timeframe)

    def _get_stock_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: "TimeFrame",
    ) -> pd.DataFrame:
        """Get historical stock bars."""
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )
        bars = self._stock_client.get_stock_bars(request)

        # Convert to DataFrame
        data = []
        for bar in bars[symbol]:
            data.append({
                "timestamp": bar.timestamp,
                "Open": float(bar.open),
                "High": float(bar.high),
                "Low": float(bar.low),
                "Close": float(bar.close),
                "Volume": int(bar.volume),
            })

        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index("timestamp", inplace=True)
        return df

    def _get_crypto_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: "TimeFrame",
    ) -> pd.DataFrame:
        """Get historical crypto bars."""
        # Normalize symbol
        if "/" not in symbol:
            symbol = f"{symbol[:3]}/{symbol[3:]}" if len(symbol) == 6 else f"{symbol}/USD"

        request = CryptoBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )
        bars = self._crypto_client.get_crypto_bars(request)

        data = []
        for bar in bars[symbol]:
            data.append({
                "timestamp": bar.timestamp,
                "Open": float(bar.open),
                "High": float(bar.high),
                "Low": float(bar.low),
                "Close": float(bar.close),
                "Volume": float(bar.volume),
            })

        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index("timestamp", inplace=True)
        return df

    def get_expirations(self, symbol: str) -> list[datetime]:
        """
        Get available option expiration dates.

        Note: Use YahooDataProvider for options chain data,
        as Alpaca's options data API availability varies.
        """
        # Alpaca options data requires separate subscription
        # Delegate to Yahoo for now
        from qwen.data.yahoo import YahooDataProvider
        return YahooDataProvider().get_expirations(symbol)

    def get_options_chain(
        self,
        symbol: str,
        expiration: Optional[datetime] = None,
    ) -> list[OptionContract]:
        """
        Get options chain.

        Note: Uses Yahoo Finance for options data.
        """
        from qwen.data.yahoo import YahooDataProvider
        return YahooDataProvider().get_options_chain(symbol, expiration)

    def get_latest_bar(self, symbol: str) -> dict:
        """Get the most recent bar for a symbol."""
        end = datetime.now()
        start = end - timedelta(days=5)

        df = self.get_historical(symbol, start, end, "1d")
        if df.empty:
            return {}

        latest = df.iloc[-1]
        return {
            "open": latest["Open"],
            "high": latest["High"],
            "low": latest["Low"],
            "close": latest["Close"],
            "volume": latest["Volume"],
            "timestamp": df.index[-1],
        }

    def __repr__(self) -> str:
        return "AlpacaDataProvider()"
