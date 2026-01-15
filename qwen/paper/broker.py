"""Simulated broker for paper trading."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Callable
import uuid

from qwen.paper.account import PaperAccount
from qwen.config import config


class OrderType(Enum):
    """Order types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(Enum):
    """Order status."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Represents a trading order."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: str = ""
    side: str = "buy"  # 'buy' or 'sell'
    quantity: float = 0
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0
    filled_price: float = 0
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    commission: float = 0

    @property
    def is_buy(self) -> bool:
        return self.side == "buy"

    @property
    def is_sell(self) -> bool:
        return self.side == "sell"

    @property
    def remaining_quantity(self) -> float:
        return self.quantity - self.filled_quantity


class PaperBroker:
    """
    Simulated broker for executing paper trades.

    Features:
    - Market and limit orders
    - Configurable slippage and commission
    - Order book tracking
    """

    def __init__(
        self,
        account: PaperAccount,
        slippage: float = None,
        commission: float = None,
        price_provider: Optional[Callable[[str], float]] = None,
    ):
        """
        Initialize paper broker.

        Args:
            account: Paper trading account
            slippage: Slippage rate (default from config)
            commission: Commission per trade (default from config)
            price_provider: Function to get current price for a symbol
        """
        self.account = account
        self.slippage = slippage if slippage is not None else config.default_slippage
        self.commission = commission if commission is not None else config.default_commission
        self.price_provider = price_provider

        self.orders: list[Order] = []
        self.pending_orders: list[Order] = []

    def _apply_slippage(self, price: float, side: str) -> float:
        """Apply slippage to price."""
        if side == "buy":
            return price * (1 + self.slippage)
        else:
            return price * (1 - self.slippage)

    def _get_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        if self.price_provider:
            return self.price_provider(symbol)
        return None

    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """
        Submit a new order.

        Args:
            symbol: Security symbol
            side: 'buy' or 'sell'
            quantity: Number of shares/contracts
            order_type: Type of order
            limit_price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)

        Returns:
            Order object
        """
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            commission=self.commission,
        )

        self.orders.append(order)

        if order_type == OrderType.MARKET:
            # Execute immediately if price available
            price = self._get_price(symbol)
            if price:
                self._execute_order(order, price)
            else:
                self.pending_orders.append(order)
        else:
            self.pending_orders.append(order)

        return order

    def market_buy(self, symbol: str, quantity: float, price: Optional[float] = None) -> Order:
        """
        Submit a market buy order.

        Args:
            symbol: Security symbol
            quantity: Number of shares to buy
            price: Execution price (if not using price provider)

        Returns:
            Executed order
        """
        order = self.submit_order(symbol, "buy", quantity, OrderType.MARKET)

        if price and order.status == OrderStatus.PENDING:
            self._execute_order(order, price)

        return order

    def market_sell(self, symbol: str, quantity: float, price: Optional[float] = None) -> Order:
        """
        Submit a market sell order.

        Args:
            symbol: Security symbol
            quantity: Number of shares to sell
            price: Execution price (if not using price provider)

        Returns:
            Executed order
        """
        order = self.submit_order(symbol, "sell", quantity, OrderType.MARKET)

        if price and order.status == OrderStatus.PENDING:
            self._execute_order(order, price)

        return order

    def limit_buy(self, symbol: str, quantity: float, limit_price: float) -> Order:
        """Submit a limit buy order."""
        return self.submit_order(symbol, "buy", quantity, OrderType.LIMIT, limit_price=limit_price)

    def limit_sell(self, symbol: str, quantity: float, limit_price: float) -> Order:
        """Submit a limit sell order."""
        return self.submit_order(symbol, "sell", quantity, OrderType.LIMIT, limit_price=limit_price)

    def _execute_order(self, order: Order, market_price: float) -> bool:
        """
        Execute an order at the given market price.

        Returns:
            True if order was executed
        """
        # Apply slippage
        fill_price = self._apply_slippage(market_price, order.side)

        # Execute trade on account
        if order.side == "buy":
            success = self.account.buy(
                order.symbol,
                order.quantity,
                fill_price,
                order.commission,
            )
        else:
            success = self.account.sell(
                order.symbol,
                order.quantity,
                fill_price,
                order.commission,
            )

        if success:
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.filled_price = fill_price
            order.filled_at = datetime.now()

            # Remove from pending
            if order in self.pending_orders:
                self.pending_orders.remove(order)

            return True
        else:
            order.status = OrderStatus.REJECTED
            return False

    def process_pending_orders(self, prices: dict[str, float]):
        """
        Process pending orders against current prices.

        Args:
            prices: Current prices for securities
        """
        for order in self.pending_orders[:]:  # Copy list to allow modification
            if order.symbol not in prices:
                continue

            price = prices[order.symbol]

            if order.order_type == OrderType.MARKET:
                self._execute_order(order, price)

            elif order.order_type == OrderType.LIMIT:
                if order.side == "buy" and price <= order.limit_price:
                    self._execute_order(order, order.limit_price)
                elif order.side == "sell" and price >= order.limit_price:
                    self._execute_order(order, order.limit_price)

            elif order.order_type == OrderType.STOP:
                if order.side == "buy" and price >= order.stop_price:
                    self._execute_order(order, price)
                elif order.side == "sell" and price <= order.stop_price:
                    self._execute_order(order, price)

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.

        Returns:
            True if order was cancelled
        """
        for order in self.pending_orders:
            if order.id == order_id:
                order.status = OrderStatus.CANCELLED
                self.pending_orders.remove(order)
                return True
        return False

    def cancel_all_orders(self, symbol: Optional[str] = None):
        """Cancel all pending orders, optionally for a specific symbol."""
        for order in self.pending_orders[:]:
            if symbol is None or order.symbol == symbol:
                order.status = OrderStatus.CANCELLED
                self.pending_orders.remove(order)

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        for order in self.orders:
            if order.id == order_id:
                return order
        return None

    def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        """Get all open/pending orders."""
        if symbol:
            return [o for o in self.pending_orders if o.symbol == symbol]
        return self.pending_orders.copy()

    def get_filled_orders(self, symbol: Optional[str] = None) -> list[Order]:
        """Get all filled orders."""
        filled = [o for o in self.orders if o.status == OrderStatus.FILLED]
        if symbol:
            return [o for o in filled if o.symbol == symbol]
        return filled
