"""Base portfolio interface for consistent portfolio tracking across modules."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd


@dataclass
class BasePosition:
    """
    Base position data class.

    Implementations may extend this with additional fields.
    """

    symbol: str
    quantity: float
    avg_cost: float

    @property
    def cost_basis(self) -> float:
        """Total cost basis of position."""
        return abs(self.quantity) * self.avg_cost

    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.quantity < 0


class BasePortfolio(ABC):
    """
    Abstract base class for portfolio tracking.

    Provides a consistent interface for portfolio operations across:
    - Backtesting (qwen.backtest.Portfolio)
    - Paper trading (qwen.paper.PaperAccount)
    - Live tracking (qwen.portfolio.PortfolioTracker)

    Implementations must provide position tracking, cash management,
    and trade execution capabilities.
    """

    @property
    @abstractmethod
    def cash(self) -> float:
        """Current cash balance."""
        pass

    @property
    @abstractmethod
    def initial_cash(self) -> float:
        """Starting cash balance."""
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[BasePosition]:
        """
        Get position for a symbol.

        Args:
            symbol: Security symbol

        Returns:
            Position object or None if not held
        """
        pass

    @abstractmethod
    def get_quantity(self, symbol: str) -> float:
        """
        Get quantity held for a symbol.

        Args:
            symbol: Security symbol

        Returns:
            Quantity (0 if not held)
        """
        pass

    @abstractmethod
    def get_all_positions(self) -> dict[str, BasePosition]:
        """
        Get all open positions.

        Returns:
            Dictionary mapping symbol to position
        """
        pass

    @abstractmethod
    def portfolio_value(self, prices: dict[str, float]) -> float:
        """
        Calculate total portfolio value.

        Args:
            prices: Current prices for held securities

        Returns:
            Total portfolio value (cash + positions)
        """
        pass

    @abstractmethod
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
            quantity: Number of shares/contracts
            price: Price per share/contract
            commission: Commission for the trade
            timestamp: Trade timestamp

        Returns:
            True if trade executed successfully
        """
        pass

    @abstractmethod
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
            quantity: Number of shares/contracts
            price: Price per share/contract
            commission: Commission for the trade
            timestamp: Trade timestamp

        Returns:
            True if trade executed successfully
        """
        pass

    # Default implementations for common operations

    def has_position(self, symbol: str) -> bool:
        """Check if we have an open position in a symbol."""
        return self.get_quantity(symbol) != 0

    def total_pnl(self, prices: dict[str, float]) -> float:
        """Calculate total P&L since inception."""
        return self.portfolio_value(prices) - self.initial_cash

    def total_return(self, prices: dict[str, float]) -> float:
        """Calculate total return as decimal."""
        if self.initial_cash == 0:
            return 0.0
        return self.total_pnl(prices) / self.initial_cash

    def positions_df(self, prices: Optional[dict[str, float]] = None) -> pd.DataFrame:
        """
        Get positions as DataFrame.

        Args:
            prices: Current prices for P&L calculation

        Returns:
            DataFrame with position details
        """
        positions = self.get_all_positions()
        if not positions:
            return pd.DataFrame(
                columns=["symbol", "quantity", "avg_cost", "current_price", "market_value", "unrealized_pnl"]
            )

        prices = prices or {}
        data = []
        for symbol, pos in positions.items():
            current_price = prices.get(symbol, pos.avg_cost)
            market_value = pos.quantity * current_price
            unrealized_pnl = pos.quantity * (current_price - pos.avg_cost)

            data.append({
                "symbol": symbol,
                "quantity": pos.quantity,
                "avg_cost": pos.avg_cost,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
            })

        return pd.DataFrame(data)
