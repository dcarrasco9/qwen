"""Yahoo Finance data provider using yfinance."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from qwen.data.base import DataProvider, OptionContract, Quote
from qwen.utils.helpers import safe_float, safe_int

logger = logging.getLogger(__name__)


class YahooDataProvider(DataProvider):
    """Data provider using Yahoo Finance (yfinance)."""

    def __init__(self):
        self._cache: dict[str, yf.Ticker] = {}

    def _get_ticker(self, symbol: str) -> yf.Ticker:
        """Get cached ticker object."""
        if symbol not in self._cache:
            self._cache[symbol] = yf.Ticker(symbol)
        return self._cache[symbol]

    def get_quote(self, symbol: str) -> Quote:
        """Get current quote for a symbol."""
        ticker = self._get_ticker(symbol)
        info = ticker.info

        # Handle missing bid/ask in after-hours or for some securities
        bid = info.get("bid", 0) or info.get("regularMarketPrice", 0)
        ask = info.get("ask", 0) or info.get("regularMarketPrice", 0)

        return Quote(
            symbol=symbol,
            last=info.get("regularMarketPrice", 0) or info.get("previousClose", 0),
            bid=bid,
            ask=ask,
            volume=info.get("regularMarketVolume", 0),
            timestamp=datetime.now(),
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
            end: End date (default: today)
            interval: Data interval ('1d', '1h', '5m', etc.)

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
        """
        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=365)

        ticker = self._get_ticker(symbol)
        df = ticker.history(start=start, end=end, interval=interval)

        # Standardize column names
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        return df

    def get_expirations(self, symbol: str) -> list[datetime]:
        """Get available option expiration dates for a symbol."""
        ticker = self._get_ticker(symbol)
        try:
            expirations = ticker.options
            return [datetime.strptime(exp, "%Y-%m-%d") for exp in expirations]
        except Exception:
            return []

    def get_options_chain(self, symbol: str, expiration: Optional[datetime] = None) -> list[OptionContract]:
        """
        Get options chain for a symbol.

        Args:
            symbol: Underlying ticker symbol
            expiration: Specific expiration date (None for nearest expiration)

        Returns:
            List of OptionContract objects
        """
        ticker = self._get_ticker(symbol)

        try:
            expirations = ticker.options
            if not expirations:
                return []

            if expiration is None:
                exp_str = expirations[0]  # Nearest expiration
            else:
                exp_str = expiration.strftime("%Y-%m-%d")
                if exp_str not in expirations:
                    # Find closest expiration
                    exp_dates = [datetime.strptime(e, "%Y-%m-%d") for e in expirations]
                    closest = min(exp_dates, key=lambda x: abs((x - expiration).days))
                    exp_str = closest.strftime("%Y-%m-%d")

            chain = ticker.option_chain(exp_str)
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d")

            contracts = []

            # Process calls
            for _, row in chain.calls.iterrows():
                contracts.append(
                    OptionContract(
                        symbol=row["contractSymbol"],
                        underlying=symbol,
                        strike=row["strike"],
                        expiration=exp_date,
                        option_type="call",
                        bid=safe_float(row.get("bid")),
                        ask=safe_float(row.get("ask")),
                        last=safe_float(row.get("lastPrice")),
                        volume=safe_int(row.get("volume")),
                        open_interest=safe_int(row.get("openInterest")),
                        implied_volatility=safe_float(row.get("impliedVolatility")),
                    )
                )

            # Process puts
            for _, row in chain.puts.iterrows():
                contracts.append(
                    OptionContract(
                        symbol=row["contractSymbol"],
                        underlying=symbol,
                        strike=row["strike"],
                        expiration=exp_date,
                        option_type="put",
                        bid=safe_float(row.get("bid")),
                        ask=safe_float(row.get("ask")),
                        last=safe_float(row.get("lastPrice")),
                        volume=safe_int(row.get("volume")),
                        open_interest=safe_int(row.get("openInterest")),
                        implied_volatility=safe_float(row.get("impliedVolatility")),
                    )
                )

            return contracts

        except Exception as e:
            logger.error(f"Error fetching options chain: {e}")
            return []

    def get_risk_free_rate(self) -> float:
        """
        Get approximate risk-free rate from Treasury yields.

        Returns:
            Current 13-week T-bill rate as a decimal
        """
        try:
            # ^IRX is the 13-week Treasury Bill rate
            ticker = self._get_ticker("^IRX")
            info = ticker.info
            rate = info.get("regularMarketPrice", 5.0)  # Default 5%
            return rate / 100  # Convert percentage to decimal
        except Exception:
            return 0.05  # Default to 5%
