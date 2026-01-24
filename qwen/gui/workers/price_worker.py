"""Background worker for fetching stock prices."""

import logging
from PySide6.QtCore import Signal, QObject

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not installed - price fetching disabled")


class PriceWorker(QObject):
    """Worker for fetching stock prices in background thread.

    Emits:
        prices_ready: Dict of ticker -> price data when fetch completes
        error: Error message string if fetch fails
    """

    prices_ready = Signal(dict)
    error = Signal(str)

    def __init__(self, tickers: list[str]):
        """
        Initialize price worker.

        Args:
            tickers: List of ticker symbols to fetch
        """
        super().__init__()
        self.tickers = tickers
        self._running = True

    def fetch_prices(self):
        """Fetch prices for all tickers. Call from background thread."""
        if not YFINANCE_AVAILABLE:
            self.error.emit("yfinance not installed")
            return

        if not self._running:
            return

        try:
            prices = {}
            tickers_str = " ".join(self.tickers)
            logger.info(f"Fetching prices for {len(self.tickers)} tickers")

            data = yf.download(
                tickers_str,
                period="2d",
                progress=False,
                group_by='ticker',
                threads=True
            )

            for ticker in self.tickers:
                if not self._running:
                    return
                try:
                    if len(self.tickers) == 1:
                        ticker_data = data
                    else:
                        ticker_data = data[ticker]

                    if ticker_data.empty or len(ticker_data) < 1:
                        logger.warning(f"No data available for {ticker}")
                        continue

                    current = float(ticker_data['Close'].iloc[-1])

                    if len(ticker_data) >= 2:
                        prev_close = float(ticker_data['Close'].iloc[-2])
                    else:
                        prev_close = float(ticker_data['Open'].iloc[-1])

                    change = current - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0

                    prices[ticker] = {
                        "price": current,
                        "change": change,
                        "change_pct": change_pct,
                    }
                except Exception as e:
                    logger.warning(f"Failed to fetch price for {ticker}: {e}")
                    continue

            if self._running:
                logger.info(f"Successfully fetched {len(prices)} prices")
                self.prices_ready.emit(prices)

        except Exception as e:
            logger.error(f"Price fetch failed: {e}")
            if self._running:
                self.error.emit(str(e))

    def stop(self):
        """Stop the worker. Safe to call from any thread."""
        self._running = False
