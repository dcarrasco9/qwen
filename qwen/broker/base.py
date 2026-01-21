"""Base classes for broker integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

# Import canonical types from unified types module
from qwen.types import AssetClass, OrderSide, OrderStatus, OrderType

# Re-export for backward compatibility
__all__ = [
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "AssetClass",
    "BrokerOrder",
    "BrokerPosition",
    "AccountInfo",
    "BaseBroker",
]


@dataclass
class BrokerOrder:
    """Represents an order from a broker."""

    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    qty: float
    filled_qty: float
    status: OrderStatus
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_avg_price: Optional[float] = None
    created_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    asset_class: AssetClass = AssetClass.STOCK

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_open(self) -> bool:
        return self.status in (OrderStatus.NEW, OrderStatus.PENDING, OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED)


@dataclass
class BrokerPosition:
    """Represents a position from a broker."""

    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float
    unrealized_pl: float
    unrealized_plpc: float  # Percentage
    current_price: float
    asset_class: AssetClass = AssetClass.STOCK

    @property
    def cost_basis(self) -> float:
        return abs(self.qty) * self.avg_entry_price

    @property
    def is_long(self) -> bool:
        return self.qty > 0

    @property
    def is_short(self) -> bool:
        return self.qty < 0


@dataclass
class AccountInfo:
    """Account information from broker."""

    account_id: str
    cash: float
    portfolio_value: float
    buying_power: float
    equity: float
    last_equity: float
    long_market_value: float
    short_market_value: float
    initial_margin: float
    maintenance_margin: float
    daytrade_count: int
    is_paper: bool = True

    @property
    def day_pl(self) -> float:
        return self.equity - self.last_equity

    @property
    def day_pl_pct(self) -> float:
        if self.last_equity == 0:
            return 0
        return (self.equity - self.last_equity) / self.last_equity


class BaseBroker(ABC):
    """Abstract base class for broker integrations."""

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """Get account information."""
        pass

    @abstractmethod
    def get_positions(self) -> list[BrokerPosition]:
        """Get all open positions."""
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[BrokerPosition]:
        """Get position for a specific symbol."""
        pass

    @abstractmethod
    def get_orders(self, status: Optional[str] = None) -> list[BrokerOrder]:
        """Get orders, optionally filtered by status."""
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[BrokerOrder]:
        """Get a specific order by ID."""
        pass

    @abstractmethod
    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: Literal["buy", "sell"],
        order_type: Literal["market", "limit", "stop", "stop_limit"] = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> BrokerOrder:
        """Submit a new order."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        pass

    @abstractmethod
    def cancel_all_orders(self) -> int:
        """Cancel all open orders. Returns count of cancelled orders."""
        pass

    # Convenience methods
    def market_buy(self, symbol: str, qty: float) -> BrokerOrder:
        """Submit a market buy order."""
        return self.submit_order(symbol, qty, "buy", "market")

    def market_sell(self, symbol: str, qty: float) -> BrokerOrder:
        """Submit a market sell order."""
        return self.submit_order(symbol, qty, "sell", "market")

    def limit_buy(self, symbol: str, qty: float, price: float) -> BrokerOrder:
        """Submit a limit buy order."""
        return self.submit_order(symbol, qty, "buy", "limit", limit_price=price)

    def limit_sell(self, symbol: str, qty: float, price: float) -> BrokerOrder:
        """Submit a limit sell order."""
        return self.submit_order(symbol, qty, "sell", "limit", limit_price=price)

    def close_position(self, symbol: str) -> Optional[BrokerOrder]:
        """Close entire position for a symbol."""
        pos = self.get_position(symbol)
        if pos is None or pos.qty == 0:
            return None

        if pos.qty > 0:
            return self.market_sell(symbol, pos.qty)
        else:
            return self.market_buy(symbol, abs(pos.qty))

    def close_all_positions(self) -> list[BrokerOrder]:
        """Close all open positions."""
        orders = []
        for pos in self.get_positions():
            order = self.close_position(pos.symbol)
            if order:
                orders.append(order)
        return orders
