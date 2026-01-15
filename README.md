# Qwen

Financial modeling toolkit for backtesting, options pricing, and paper trading.

## Installation

```bash
cd qwen
pip install -e .

# With all optional dependencies
pip install -e ".[all]"
```

## Quick Start

### Options Pricing

```python
from qwen.pricing import BlackScholes

# Price a call option
bs = BlackScholes(
    spot=150,          # Current stock price
    strike=155,        # Strike price
    rate=0.05,         # Risk-free rate (5%)
    volatility=0.25,   # Volatility (25%)
    time_to_expiry=0.25  # 3 months
)

print(f"Call: ${bs.call_price():.2f}")
print(f"Delta: {bs.delta('call'):.4f}")

# Get all Greeks
greeks = bs.greeks("call")
```

### Market Data

```python
from qwen.data import YahooDataProvider

provider = YahooDataProvider()

# Get quote
quote = provider.get_quote("AAPL")
print(f"AAPL: ${quote.last}")

# Get historical data
hist = provider.get_historical("AAPL")

# Get options chain
chain = provider.get_options_chain("AAPL")
```

### Backtesting

```python
from qwen.backtest import BacktestEngine
from qwen.backtest.strategy import SimpleMovingAverageCrossover
from qwen.data import YahooDataProvider

# Get data
provider = YahooDataProvider()
data = provider.get_historical("AAPL")

# Create strategy
strategy = SimpleMovingAverageCrossover("AAPL", short_window=20, long_window=50)

# Run backtest
engine = BacktestEngine(initial_capital=100_000)
result = engine.run(strategy, data, symbol="AAPL")

print(f"Total Return: {result.total_return:.2%}")
print(f"Sharpe Ratio: {result.metrics.sharpe_ratio:.2f}")

# Plot results
result.plot()
```

### Paper Trading

```python
from qwen.paper import PaperAccount, PaperBroker

account = PaperAccount(starting_balance=100_000)
broker = PaperBroker(account)

# Execute trades
broker.market_buy("AAPL", 100, price=150.0)
broker.market_sell("AAPL", 50, price=155.0)

# Check portfolio
print(account.summary({"AAPL": 155.0}))
```

## Components

### Data (`qwen.data`)
- `YahooDataProvider` - Free historical data via yfinance
- `SchwabDataProvider` - Real-time data (requires API credentials)

### Pricing (`qwen.pricing`)
- `BlackScholes` - Analytical pricing with Greeks
- `BinomialTree` - American option support
- `MonteCarlo` - Exotic options (Asian, barrier)

### Backtesting (`qwen.backtest`)
- `BacktestEngine` - Event-driven backtest runner
- `Strategy` - Base class for custom strategies
- `PerformanceMetrics` - Sharpe, Sortino, max drawdown, etc.

### Paper Trading (`qwen.paper`)
- `PaperAccount` - Virtual account management
- `PaperBroker` - Simulated order execution

## Configuration

Set environment variables for Schwab API:
```bash
export SCHWAB_API_KEY="your_key"
export SCHWAB_API_SECRET="your_secret"
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

## Examples

See `strategies/` for example strategies and `notebooks/exploration.ipynb` for interactive examples.
