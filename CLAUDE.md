# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install in development mode
pip install -e .

# Install with all optional dependencies (Alpaca, Schwab, dev tools)
pip install -e ".[all]"

# Run all tests
pytest

# Run a specific test file
pytest tests/test_pricing.py

# Run a specific test
pytest tests/test_pricing.py::TestBlackScholes::test_call_price_atm -v
```

## Architecture Overview

Qwen is a financial modeling toolkit with a modular architecture organized around these core components:

### Data Layer (`qwen/data/`)
Abstract `DataProvider` base class with implementations for different market data sources:
- `YahooDataProvider` - Free historical data via yfinance (always available)
- `AlpacaDataProvider` - Real-time data (optional, requires `alpaca-py`)
- `SchwabDataProvider` - Real-time data (optional, requires `schwab-py`)

Providers return standardized data structures: `Quote` for current prices, `OptionContract` for options chains, and pandas DataFrames with OHLCV columns for historical data.

### Pricing Models (`qwen/pricing/`)
Options pricing implementations:
- `BlackScholes` - Analytical pricing with full Greeks (delta, gamma, theta, vega, rho)
- `BinomialTree` - Supports both American and European options
- `MonteCarlo` - Exotic options (Asian, barrier), returns confidence intervals

### Backtesting Engine (`qwen/backtest/`)
Event-driven backtesting system:
- `Strategy` - Abstract base class; implement `on_bar()` to define trading logic
- `Signal` - Data class for trading signals (buy/sell/hold with metadata)
- `BacktestEngine` - Executes strategies against historical data
- `Portfolio` - Position tracking during backtests
- `PerformanceMetrics` - Sharpe, Sortino, max drawdown calculations

### Broker Integrations (`qwen/broker/`)
Abstract `BaseBroker` defines the interface for live trading. Key data classes:
- `BrokerOrder`, `BrokerPosition`, `AccountInfo`
- `AlpacaBroker` - Alpaca trading API implementation
- `AlpacaOptionsBroker` - Options trading via Alpaca

### Paper Trading (`qwen/paper/`)
Simulated trading for strategy testing:
- `PaperAccount` - Virtual account with position tracking
- `PaperBroker` - Simulated order execution

### Screeners (`qwen/screener/`)
- `MispricingScanner` - Detects options mispricing vs theoretical values
- `VolatilityAnalyzer` - IV analysis and skew detection

### Portfolio Management (`qwen/portfolio/`)
- `IncomeBasedAllocator` - Allocation based on income parameters
- `PortfolioTracker` - Position and P&L tracking

## Configuration

API credentials are loaded from environment variables via `qwen/config.py`:
- `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER` (default: true)
- `SCHWAB_API_KEY`, `SCHWAB_API_SECRET`, `SCHWAB_CALLBACK_URL`

Create a `.env` file in the project root for local development.

## Creating Custom Strategies

Extend `Strategy` and implement `on_bar()`:

```python
from qwen.backtest import Strategy, Signal

class MyStrategy(Strategy):
    def on_bar(self, bar: pd.Series) -> list[Signal]:
        # Access historical data via self.history
        # Access portfolio via self.portfolio
        # Return list of Signal objects
        return [self.buy("AAPL", reason="entry signal")]
```

Use `on_start()` and `on_end()` hooks for setup/teardown. See `strategies/` directory for examples.
