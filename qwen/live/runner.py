"""Live trading runner for executing strategies against real brokers."""

from datetime import datetime
from typing import Optional
import pandas as pd

from qwen.broker.base import BaseBroker, BrokerOrder
from qwen.broker.alpaca_broker import AlpacaBroker
from qwen.backtest.strategy import Strategy, Signal
from qwen.data.base import DataProvider


class LiveRunner:
    """
    Execute trading strategies against a live/paper broker.

    This runner connects your backtested strategies to real market execution.
    """

    def __init__(
        self,
        broker: BaseBroker,
        data_provider: Optional[DataProvider] = None,
        default_qty: float = 1,
        max_position_pct: float = 0.10,  # Max 10% of portfolio per position
    ):
        """
        Initialize live runner.

        Args:
            broker: Broker for order execution
            data_provider: Data provider for market data (optional, uses broker data if not provided)
            default_qty: Default quantity when strategy doesn't specify
            max_position_pct: Maximum position size as % of portfolio
        """
        self.broker = broker
        self.data_provider = data_provider
        self.default_qty = default_qty
        self.max_position_pct = max_position_pct

        self._strategies: dict[str, Strategy] = {}
        self._last_run: Optional[datetime] = None
        self._trade_log: list[dict] = []

    def add_strategy(self, strategy: Strategy, symbols: list[str]):
        """
        Add a strategy to run.

        Args:
            strategy: Strategy instance
            symbols: List of symbols this strategy trades
        """
        strategy._symbols = symbols
        self._strategies[strategy.name] = strategy

    def run_once(
        self,
        strategy: Strategy,
        symbol: str,
        lookback_days: int = 60,
    ) -> list[BrokerOrder]:
        """
        Run a strategy once with current market data.

        Args:
            strategy: Strategy to execute
            symbol: Symbol to trade
            lookback_days: Days of historical data for strategy

        Returns:
            List of orders submitted
        """
        orders = []

        # Get historical data for strategy context
        if self.data_provider:
            from datetime import timedelta
            end = datetime.now()
            start = end - timedelta(days=lookback_days)
            history = self.data_provider.get_historical(symbol, start, end)
        else:
            # Try to get from broker if it supports data
            if hasattr(self.broker, 'get_historical'):
                history = self.broker.get_historical(symbol, lookback_days)
            else:
                # Fallback to Yahoo
                from qwen.data.yahoo import YahooDataProvider
                from datetime import timedelta
                provider = YahooDataProvider()
                end = datetime.now()
                start = end - timedelta(days=lookback_days)
                history = provider.get_historical(symbol, start, end)

        if history.empty:
            print(f"Warning: No historical data for {symbol}")
            return orders

        # Set up strategy context
        # Create a mock portfolio that reflects current broker positions
        from qwen.backtest.portfolio import Portfolio
        account = self.broker.get_account()
        portfolio = Portfolio(initial_cash=account.cash)

        # Add current positions to portfolio
        for pos in self.broker.get_positions():
            if pos.symbol == symbol:
                portfolio.positions[pos.symbol] = type('Position', (), {
                    'quantity': pos.qty,
                    'avg_cost': pos.avg_entry_price,
                })()

        strategy._portfolio = portfolio
        strategy._history = history

        # Run strategy on latest bar
        latest_bar = history.iloc[-1]
        signals = strategy.on_bar(latest_bar)

        # Execute signals
        for signal in signals:
            if signal.action == "hold":
                continue

            order = self._execute_signal(signal, symbol, latest_bar["Close"])
            if order:
                orders.append(order)
                self._log_trade(signal, order, symbol)

        self._last_run = datetime.now()
        return orders

    def _execute_signal(
        self,
        signal: Signal,
        symbol: str,
        current_price: float,
    ) -> Optional[BrokerOrder]:
        """Execute a trading signal."""
        sig_symbol = signal.symbol or symbol

        # Determine quantity
        if signal.quantity:
            qty = signal.quantity
        else:
            # Position sizing based on portfolio
            account = self.broker.get_account()
            max_position_value = account.portfolio_value * self.max_position_pct
            qty = int(max_position_value / current_price)
            qty = max(qty, self.default_qty)

        if qty <= 0:
            return None

        try:
            if signal.action == "buy":
                if signal.price:
                    order = self.broker.limit_buy(sig_symbol, qty, signal.price)
                else:
                    order = self.broker.market_buy(sig_symbol, qty)
            elif signal.action == "sell":
                # Check if we have position
                pos = self.broker.get_position(sig_symbol)
                if pos and pos.qty > 0:
                    sell_qty = min(qty, pos.qty)
                    if signal.price:
                        order = self.broker.limit_sell(sig_symbol, sell_qty, signal.price)
                    else:
                        order = self.broker.market_sell(sig_symbol, sell_qty)
                else:
                    print(f"No position to sell for {sig_symbol}")
                    return None
            else:
                return None

            print(f"Order submitted: {signal.action.upper()} {qty} {sig_symbol} - {order.status.value}")
            return order

        except Exception as e:
            print(f"Error executing signal: {e}")
            return None

    def _log_trade(self, signal: Signal, order: BrokerOrder, symbol: str):
        """Log trade for tracking."""
        self._trade_log.append({
            "timestamp": datetime.now(),
            "symbol": symbol,
            "action": signal.action,
            "quantity": order.qty,
            "order_id": order.id,
            "status": order.status.value,
            "reason": signal.reason,
        })

    def get_status(self) -> dict:
        """Get current trading status."""
        account = self.broker.get_account()
        positions = self.broker.get_positions()

        return {
            "last_run": self._last_run,
            "account": {
                "equity": account.equity,
                "cash": account.cash,
                "buying_power": account.buying_power,
                "day_pl": account.day_pl,
                "day_pl_pct": account.day_pl_pct * 100,
            },
            "positions": [
                {
                    "symbol": p.symbol,
                    "qty": p.qty,
                    "market_value": p.market_value,
                    "unrealized_pl": p.unrealized_pl,
                    "unrealized_pl_pct": p.unrealized_plpc * 100,
                }
                for p in positions
            ],
            "num_trades_today": len([
                t for t in self._trade_log
                if t["timestamp"].date() == datetime.now().date()
            ]),
        }

    def get_trade_log(self) -> pd.DataFrame:
        """Get trade log as DataFrame."""
        if not self._trade_log:
            return pd.DataFrame()
        return pd.DataFrame(self._trade_log)

    def emergency_close_all(self) -> list[BrokerOrder]:
        """
        Emergency close all positions.

        Use this to quickly exit all positions.
        """
        print("EMERGENCY CLOSE: Closing all positions...")

        # Cancel all open orders first
        cancelled = self.broker.cancel_all_orders()
        print(f"Cancelled {cancelled} open orders")

        # Close all positions
        orders = self.broker.close_all_positions()
        for order in orders:
            print(f"Closing {order.symbol}: {order.status.value}")

        return orders

    def print_status(self):
        """Print current status to console."""
        status = self.get_status()

        print("\n" + "=" * 50)
        print("LIVE TRADING STATUS")
        print("=" * 50)

        print(f"\nAccount:")
        print(f"  Equity:       ${status['account']['equity']:,.2f}")
        print(f"  Cash:         ${status['account']['cash']:,.2f}")
        print(f"  Buying Power: ${status['account']['buying_power']:,.2f}")
        print(f"  Day P&L:      ${status['account']['day_pl']:+,.2f} ({status['account']['day_pl_pct']:+.2f}%)")

        print(f"\nPositions ({len(status['positions'])}):")
        if status['positions']:
            for p in status['positions']:
                print(f"  {p['symbol']:6} {p['qty']:>6} shares  ${p['market_value']:>10,.2f}  P&L: ${p['unrealized_pl']:>+8,.2f} ({p['unrealized_pl_pct']:>+6.2f}%)")
        else:
            print("  No open positions")

        print(f"\nLast Run: {status['last_run']}")
        print(f"Trades Today: {status['num_trades_today']}")
        print("=" * 50)
