"""Paper trading account management."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import pandas as pd


@dataclass
class Position:
    """Represents a position in a security."""

    symbol: str
    quantity: float  # Positive for long, negative for short
    cost_basis: float  # Average cost per share
    opened_at: datetime = field(default_factory=datetime.now)

    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.quantity < 0

    @property
    def total_cost(self) -> float:
        """Total cost basis of position."""
        return abs(self.quantity) * self.cost_basis

    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L at current price."""
        return self.quantity * (current_price - self.cost_basis)

    def unrealized_pnl_percent(self, current_price: float) -> float:
        """Calculate unrealized P&L percentage."""
        if self.cost_basis == 0:
            return 0.0
        if self.is_long:
            return (current_price - self.cost_basis) / self.cost_basis
        else:
            return (self.cost_basis - current_price) / self.cost_basis


@dataclass
class Trade:
    """Record of a completed trade."""

    symbol: str
    quantity: float
    price: float
    timestamp: datetime
    commission: float = 0.0
    side: str = "buy"  # 'buy' or 'sell'

    @property
    def total_value(self) -> float:
        """Total value of trade including commission."""
        return abs(self.quantity) * self.price + self.commission


class PaperAccount:
    """
    Simulated trading account for paper trading.

    Tracks cash balance, positions, and trade history.
    """

    def __init__(self, starting_balance: float = 100_000.0):
        """
        Initialize paper trading account.

        Args:
            starting_balance: Initial cash balance
        """
        self.starting_balance = starting_balance
        self.cash = starting_balance
        self.positions: dict[str, Position] = {}
        self.trade_history: list[Trade] = []
        self._equity_history: list[tuple[datetime, float]] = []

    @property
    def position_symbols(self) -> list[str]:
        """Get list of symbols with open positions."""
        return list(self.positions.keys())

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol, or None if not held."""
        return self.positions.get(symbol)

    def get_quantity(self, symbol: str) -> float:
        """Get quantity held for a symbol (0 if not held)."""
        pos = self.positions.get(symbol)
        return pos.quantity if pos else 0

    def buy(
        self,
        symbol: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Execute a buy order.

        Args:
            symbol: Security symbol
            quantity: Number of shares/contracts to buy
            price: Price per share/contract
            commission: Commission for the trade
            timestamp: Trade timestamp

        Returns:
            True if trade executed, False if insufficient funds
        """
        total_cost = quantity * price + commission

        if total_cost > self.cash:
            return False

        timestamp = timestamp or datetime.now()

        # Update cash
        self.cash -= total_cost

        # Update or create position
        if symbol in self.positions:
            pos = self.positions[symbol]
            # Calculate new average cost
            total_shares = pos.quantity + quantity
            if total_shares != 0:
                new_cost_basis = (pos.quantity * pos.cost_basis + quantity * price) / total_shares
            else:
                new_cost_basis = 0
            pos.quantity = total_shares
            pos.cost_basis = new_cost_basis
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                cost_basis=price,
                opened_at=timestamp,
            )

        # Record trade
        self.trade_history.append(
            Trade(
                symbol=symbol,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
                commission=commission,
                side="buy",
            )
        )

        # Clean up zero positions
        if symbol in self.positions and self.positions[symbol].quantity == 0:
            del self.positions[symbol]

        return True

    def sell(
        self,
        symbol: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Execute a sell order.

        Args:
            symbol: Security symbol
            quantity: Number of shares/contracts to sell
            price: Price per share/contract
            commission: Commission for the trade
            timestamp: Trade timestamp

        Returns:
            True if trade executed, False if insufficient position
        """
        timestamp = timestamp or datetime.now()

        # Check if we have the position (for long sales)
        if symbol in self.positions:
            pos = self.positions[symbol]
            if pos.quantity < quantity:
                return False  # Can't sell more than we have
        else:
            # Allow short selling (negative quantity)
            pass

        proceeds = quantity * price - commission

        # Update cash
        self.cash += proceeds

        # Update position
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.quantity -= quantity
            if pos.quantity == 0:
                del self.positions[symbol]
        else:
            # Short sale
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=-quantity,
                cost_basis=price,
                opened_at=timestamp,
            )

        # Record trade
        self.trade_history.append(
            Trade(
                symbol=symbol,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
                commission=commission,
                side="sell",
            )
        )

        return True

    def portfolio_value(self, prices: dict[str, float]) -> float:
        """
        Calculate total portfolio value.

        Args:
            prices: Current prices for held securities

        Returns:
            Total portfolio value (cash + positions)
        """
        position_value = sum(
            pos.quantity * prices.get(symbol, pos.cost_basis)
            for symbol, pos in self.positions.items()
        )
        return self.cash + position_value

    def record_equity(self, prices: dict[str, float], timestamp: Optional[datetime] = None):
        """Record current equity for tracking."""
        timestamp = timestamp or datetime.now()
        equity = self.portfolio_value(prices)
        self._equity_history.append((timestamp, equity))

    def equity_curve(self) -> pd.DataFrame:
        """Get equity curve as DataFrame."""
        if not self._equity_history:
            return pd.DataFrame(columns=["timestamp", "equity"])

        df = pd.DataFrame(self._equity_history, columns=["timestamp", "equity"])
        df.set_index("timestamp", inplace=True)
        return df

    def realized_pnl(self) -> float:
        """Calculate total realized P&L from closed trades."""
        # This is a simplified calculation
        # A more accurate version would track each position's cost basis
        total_bought = sum(t.total_value for t in self.trade_history if t.side == "buy")
        total_sold = sum(t.total_value for t in self.trade_history if t.side == "sell")
        position_value = sum(pos.total_cost for pos in self.positions.values())
        return total_sold - total_bought + position_value

    def unrealized_pnl(self, prices: dict[str, float]) -> float:
        """Calculate total unrealized P&L."""
        return sum(
            pos.unrealized_pnl(prices.get(symbol, pos.cost_basis))
            for symbol, pos in self.positions.items()
        )

    def total_pnl(self, prices: dict[str, float]) -> float:
        """Calculate total P&L (realized + unrealized)."""
        return self.portfolio_value(prices) - self.starting_balance

    def summary(self, prices: Optional[dict[str, float]] = None) -> dict:
        """
        Get account summary.

        Args:
            prices: Current prices for P&L calculation

        Returns:
            Dictionary with account summary
        """
        prices = prices or {}

        return {
            "cash": self.cash,
            "positions": len(self.positions),
            "portfolio_value": self.portfolio_value(prices),
            "total_pnl": self.total_pnl(prices),
            "total_pnl_percent": self.total_pnl(prices) / self.starting_balance * 100,
            "num_trades": len(self.trade_history),
        }

    def positions_df(self, prices: Optional[dict[str, float]] = None) -> pd.DataFrame:
        """Get positions as DataFrame."""
        if not self.positions:
            return pd.DataFrame(columns=["symbol", "quantity", "cost_basis", "current_price", "unrealized_pnl"])

        prices = prices or {}
        data = []
        for symbol, pos in self.positions.items():
            current_price = prices.get(symbol, pos.cost_basis)
            data.append({
                "symbol": symbol,
                "quantity": pos.quantity,
                "cost_basis": pos.cost_basis,
                "current_price": current_price,
                "market_value": pos.quantity * current_price,
                "unrealized_pnl": pos.unrealized_pnl(current_price),
                "unrealized_pnl_pct": pos.unrealized_pnl_percent(current_price) * 100,
            })

        return pd.DataFrame(data)

    def trades_df(self) -> pd.DataFrame:
        """Get trade history as DataFrame."""
        if not self.trade_history:
            return pd.DataFrame(columns=["timestamp", "symbol", "side", "quantity", "price", "commission"])

        data = [
            {
                "timestamp": t.timestamp,
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "commission": t.commission,
                "total_value": t.total_value,
            }
            for t in self.trade_history
        ]

        return pd.DataFrame(data)
