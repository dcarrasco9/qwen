"""Portfolio tracking for backtesting."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class PortfolioPosition:
    """Position in the portfolio."""

    symbol: str
    quantity: float
    avg_cost: float
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        return abs(self.quantity) * self.avg_cost

    @property
    def unrealized_pnl(self) -> float:
        return self.quantity * (self.current_price - self.avg_cost)

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.avg_cost == 0:
            return 0.0
        return (self.current_price - self.avg_cost) / self.avg_cost


class Portfolio:
    """
    Portfolio tracker for backtesting.

    Tracks positions, cash, and performance over time.
    """

    def __init__(self, initial_cash: float = 100_000.0, commission: float = 0.0):
        """
        Initialize portfolio.

        Args:
            initial_cash: Starting cash balance
            commission: Commission per trade
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission = commission

        self.positions: dict[str, PortfolioPosition] = {}
        self.trades: list[dict] = []

        # Time series tracking
        self._equity_series: list[tuple[datetime, float]] = []
        self._cash_series: list[tuple[datetime, float]] = []

    def get_quantity(self, symbol: str) -> float:
        """Get position quantity for a symbol."""
        if symbol in self.positions:
            return self.positions[symbol].quantity
        return 0.0

    def get_position(self, symbol: str) -> Optional[PortfolioPosition]:
        """Get position object for a symbol."""
        return self.positions.get(symbol)

    def update_prices(self, prices: dict[str, float]):
        """Update current prices for all positions."""
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.current_price = prices[symbol]

    def execute_trade(
        self,
        symbol: str,
        quantity: float,
        price: float,
        timestamp: datetime,
        side: str = "buy",
    ) -> bool:
        """
        Execute a trade.

        Args:
            symbol: Security symbol
            quantity: Number of shares (positive)
            price: Execution price
            timestamp: Trade timestamp
            side: 'buy' or 'sell'

        Returns:
            True if trade was executed
        """
        trade_value = quantity * price
        commission = self.commission

        if side == "buy":
            total_cost = trade_value + commission
            if total_cost > self.cash:
                return False  # Insufficient funds

            self.cash -= total_cost

            if symbol in self.positions:
                pos = self.positions[symbol]
                # Update average cost
                total_qty = pos.quantity + quantity
                if total_qty != 0:
                    new_avg_cost = (pos.quantity * pos.avg_cost + quantity * price) / total_qty
                else:
                    new_avg_cost = 0
                pos.quantity = total_qty
                pos.avg_cost = new_avg_cost
                pos.current_price = price
            else:
                self.positions[symbol] = PortfolioPosition(
                    symbol=symbol,
                    quantity=quantity,
                    avg_cost=price,
                    current_price=price,
                )

        else:  # sell
            if symbol not in self.positions or self.positions[symbol].quantity < quantity:
                return False  # Insufficient position

            proceeds = trade_value - commission
            self.cash += proceeds

            pos = self.positions[symbol]
            pos.quantity -= quantity
            pos.current_price = price

            if pos.quantity == 0:
                del self.positions[symbol]

        # Record trade
        self.trades.append({
            "timestamp": timestamp,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "commission": commission,
            "value": trade_value,
        })

        return True

    def buy(self, symbol: str, quantity: float, price: float, timestamp: datetime) -> bool:
        """Execute a buy trade."""
        return self.execute_trade(symbol, quantity, price, timestamp, "buy")

    def sell(self, symbol: str, quantity: float, price: float, timestamp: datetime) -> bool:
        """Execute a sell trade."""
        return self.execute_trade(symbol, quantity, price, timestamp, "sell")

    @property
    def total_equity(self) -> float:
        """Calculate total portfolio equity."""
        position_value = sum(pos.market_value for pos in self.positions.values())
        return self.cash + position_value

    @property
    def total_pnl(self) -> float:
        """Total P&L since inception."""
        return self.total_equity - self.initial_cash

    @property
    def total_return(self) -> float:
        """Total return as decimal."""
        return self.total_pnl / self.initial_cash

    def record_state(self, timestamp: datetime):
        """Record current portfolio state for time series."""
        self._equity_series.append((timestamp, self.total_equity))
        self._cash_series.append((timestamp, self.cash))

    def equity_curve(self) -> pd.Series:
        """Get equity time series."""
        if not self._equity_series:
            return pd.Series(dtype=float)
        df = pd.DataFrame(self._equity_series, columns=["timestamp", "equity"])
        return df.set_index("timestamp")["equity"]

    def returns(self) -> pd.Series:
        """Get returns time series."""
        equity = self.equity_curve()
        if len(equity) < 2:
            return pd.Series(dtype=float)
        return equity.pct_change().dropna()

    def positions_summary(self) -> pd.DataFrame:
        """Get summary of current positions."""
        if not self.positions:
            return pd.DataFrame()

        data = []
        for symbol, pos in self.positions.items():
            data.append({
                "symbol": symbol,
                "quantity": pos.quantity,
                "avg_cost": pos.avg_cost,
                "current_price": pos.current_price,
                "market_value": pos.market_value,
                "unrealized_pnl": pos.unrealized_pnl,
                "unrealized_pnl_pct": pos.unrealized_pnl_pct * 100,
            })

        return pd.DataFrame(data)

    def trades_df(self) -> pd.DataFrame:
        """Get trades as DataFrame."""
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame(self.trades)

    def summary(self) -> dict:
        """Get portfolio summary."""
        return {
            "initial_cash": self.initial_cash,
            "current_cash": self.cash,
            "positions_value": sum(p.market_value for p in self.positions.values()),
            "total_equity": self.total_equity,
            "total_pnl": self.total_pnl,
            "total_return_pct": self.total_return * 100,
            "num_positions": len(self.positions),
            "num_trades": len(self.trades),
        }
