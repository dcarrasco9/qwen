"""Alpaca Markets broker integration."""

from datetime import datetime
from typing import Optional, Literal
import os

from qwen.broker.base import (
    BaseBroker,
    BrokerOrder,
    BrokerPosition,
    AccountInfo,
    OrderSide,
    OrderType,
    OrderStatus,
    AssetClass,
)
from qwen.config import config

# Import alpaca-py
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest,
        LimitOrderRequest,
        StopOrderRequest,
        StopLimitOrderRequest,
        GetOrdersRequest,
    )
    from alpaca.trading.enums import (
        OrderSide as AlpacaOrderSide,
        OrderType as AlpacaOrderType,
        TimeInForce,
        QueryOrderStatus,
        AssetClass as AlpacaAssetClass,
    )
    from alpaca.common.exceptions import APIError
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False


def _convert_order_status(status: str) -> OrderStatus:
    """Convert Alpaca order status to our OrderStatus enum."""
    mapping = {
        "new": OrderStatus.NEW,
        "pending_new": OrderStatus.PENDING,
        "accepted": OrderStatus.ACCEPTED,
        "filled": OrderStatus.FILLED,
        "partially_filled": OrderStatus.PARTIALLY_FILLED,
        "canceled": OrderStatus.CANCELED,
        "expired": OrderStatus.EXPIRED,
        "rejected": OrderStatus.REJECTED,
    }
    return mapping.get(status.lower(), OrderStatus.NEW)


def _convert_order_side(side) -> OrderSide:
    """Convert Alpaca order side to our OrderSide enum."""
    side_str = str(side).lower()
    return OrderSide.BUY if "buy" in side_str else OrderSide.SELL


def _convert_order_type(order_type: str) -> OrderType:
    """Convert Alpaca order type to our OrderType enum."""
    mapping = {
        "market": OrderType.MARKET,
        "limit": OrderType.LIMIT,
        "stop": OrderType.STOP,
        "stop_limit": OrderType.STOP_LIMIT,
        "trailing_stop": OrderType.TRAILING_STOP,
    }
    return mapping.get(order_type.lower(), OrderType.MARKET)


def _convert_asset_class(asset_class: str) -> AssetClass:
    """Convert Alpaca asset class to our AssetClass enum."""
    mapping = {
        "us_equity": AssetClass.STOCK,
        "crypto": AssetClass.CRYPTO,
        "us_option": AssetClass.OPTION,
    }
    return mapping.get(asset_class.lower(), AssetClass.STOCK)


class AlpacaBroker(BaseBroker):
    """
    Alpaca Markets broker for stocks and crypto trading.

    Supports both paper and live trading.

    Environment variables:
        ALPACA_API_KEY: Your Alpaca API key
        ALPACA_SECRET_KEY: Your Alpaca secret key
        ALPACA_PAPER: 'true' for paper trading (default), 'false' for live
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: Optional[bool] = None,
    ):
        """
        Initialize Alpaca broker.

        Args:
            api_key: Alpaca API key (or use ALPACA_API_KEY env var)
            secret_key: Alpaca secret key (or use ALPACA_SECRET_KEY env var)
            paper: Use paper trading (default True)
        """
        if not ALPACA_AVAILABLE:
            raise ImportError(
                "alpaca-py is not installed. Install with: pip install alpaca-py"
            )

        self.api_key = api_key or config.alpaca_api_key
        self.secret_key = secret_key or config.alpaca_secret_key
        self.paper = paper if paper is not None else config.alpaca_paper

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Alpaca credentials required. Set ALPACA_API_KEY and ALPACA_SECRET_KEY "
                "environment variables or pass api_key and secret_key parameters."
            )

        self._client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=self.paper,
        )

    def get_account(self) -> AccountInfo:
        """Get account information."""
        account = self._client.get_account()

        return AccountInfo(
            account_id=str(account.id),
            cash=float(account.cash),
            portfolio_value=float(account.portfolio_value),
            buying_power=float(account.buying_power),
            equity=float(account.equity),
            last_equity=float(account.last_equity),
            long_market_value=float(account.long_market_value),
            short_market_value=float(account.short_market_value),
            initial_margin=float(account.initial_margin),
            maintenance_margin=float(account.maintenance_margin),
            daytrade_count=int(account.daytrade_count),
            is_paper=self.paper,
        )

    def get_positions(self) -> list[BrokerPosition]:
        """Get all open positions."""
        positions = self._client.get_all_positions()

        return [
            BrokerPosition(
                symbol=pos.symbol,
                qty=float(pos.qty),
                avg_entry_price=float(pos.avg_entry_price),
                market_value=float(pos.market_value),
                unrealized_pl=float(pos.unrealized_pl),
                unrealized_plpc=float(pos.unrealized_plpc),
                current_price=float(pos.current_price),
                asset_class=_convert_asset_class(str(pos.asset_class)),
            )
            for pos in positions
        ]

    def get_position(self, symbol: str) -> Optional[BrokerPosition]:
        """Get position for a specific symbol."""
        try:
            pos = self._client.get_open_position(symbol)
            return BrokerPosition(
                symbol=pos.symbol,
                qty=float(pos.qty),
                avg_entry_price=float(pos.avg_entry_price),
                market_value=float(pos.market_value),
                unrealized_pl=float(pos.unrealized_pl),
                unrealized_plpc=float(pos.unrealized_plpc),
                current_price=float(pos.current_price),
                asset_class=_convert_asset_class(str(pos.asset_class)),
            )
        except APIError:
            return None

    def get_orders(self, status: Optional[str] = None) -> list[BrokerOrder]:
        """Get orders, optionally filtered by status."""
        request = GetOrdersRequest(
            status=QueryOrderStatus(status) if status else None,
        )
        orders = self._client.get_orders(request)

        return [self._convert_order(order) for order in orders]

    def get_order(self, order_id: str) -> Optional[BrokerOrder]:
        """Get a specific order by ID."""
        try:
            order = self._client.get_order_by_id(order_id)
            return self._convert_order(order)
        except APIError:
            return None

    def _convert_order(self, order) -> BrokerOrder:
        """Convert Alpaca order to BrokerOrder."""
        return BrokerOrder(
            id=str(order.id),
            symbol=order.symbol,
            side=_convert_order_side(str(order.side)),
            order_type=_convert_order_type(str(order.type)),
            qty=float(order.qty),
            filled_qty=float(order.filled_qty) if order.filled_qty else 0,
            status=_convert_order_status(str(order.status)),
            limit_price=float(order.limit_price) if order.limit_price else None,
            stop_price=float(order.stop_price) if order.stop_price else None,
            filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
            created_at=order.created_at,
            filled_at=order.filled_at,
            asset_class=_convert_asset_class(str(order.asset_class)) if order.asset_class else AssetClass.STOCK,
        )

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
        alpaca_side = AlpacaOrderSide.BUY if side == "buy" else AlpacaOrderSide.SELL

        tif_mapping = {
            "day": TimeInForce.DAY,
            "gtc": TimeInForce.GTC,
            "ioc": TimeInForce.IOC,
            "fok": TimeInForce.FOK,
        }
        alpaca_tif = tif_mapping.get(time_in_force.lower(), TimeInForce.DAY)

        if order_type == "market":
            request = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=alpaca_side,
                time_in_force=alpaca_tif,
            )
        elif order_type == "limit":
            if limit_price is None:
                raise ValueError("limit_price required for limit orders")
            request = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=alpaca_side,
                time_in_force=alpaca_tif,
                limit_price=limit_price,
            )
        elif order_type == "stop":
            if stop_price is None:
                raise ValueError("stop_price required for stop orders")
            request = StopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=alpaca_side,
                time_in_force=alpaca_tif,
                stop_price=stop_price,
            )
        elif order_type == "stop_limit":
            if limit_price is None or stop_price is None:
                raise ValueError("limit_price and stop_price required for stop_limit orders")
            request = StopLimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=alpaca_side,
                time_in_force=alpaca_tif,
                limit_price=limit_price,
                stop_price=stop_price,
            )
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

        order = self._client.submit_order(request)
        return self._convert_order(order)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            self._client.cancel_order_by_id(order_id)
            return True
        except APIError:
            return False

    def cancel_all_orders(self) -> int:
        """Cancel all open orders. Returns count of cancelled orders."""
        result = self._client.cancel_orders()
        return len(result) if result else 0

    # Crypto-specific methods
    def buy_crypto(self, symbol: str, qty: float, notional: Optional[float] = None) -> BrokerOrder:
        """
        Buy cryptocurrency.

        Args:
            symbol: Crypto symbol (e.g., 'BTC/USD', 'ETH/USD')
            qty: Quantity to buy (in crypto units)
            notional: Dollar amount to buy (alternative to qty)
        """
        # Crypto symbols use slash notation
        if "/" not in symbol:
            symbol = f"{symbol}/USD"

        return self.market_buy(symbol, qty)

    def sell_crypto(self, symbol: str, qty: float) -> BrokerOrder:
        """
        Sell cryptocurrency.

        Args:
            symbol: Crypto symbol (e.g., 'BTC/USD', 'ETH/USD')
            qty: Quantity to sell
        """
        if "/" not in symbol:
            symbol = f"{symbol}/USD"

        return self.market_sell(symbol, qty)

    def get_crypto_positions(self) -> list[BrokerPosition]:
        """Get all crypto positions."""
        return [
            pos for pos in self.get_positions()
            if pos.asset_class == AssetClass.CRYPTO
        ]

    def get_stock_positions(self) -> list[BrokerPosition]:
        """Get all stock positions."""
        return [
            pos for pos in self.get_positions()
            if pos.asset_class == AssetClass.STOCK
        ]

    # Status methods
    def is_market_open(self) -> bool:
        """Check if US stock market is currently open."""
        clock = self._client.get_clock()
        return clock.is_open

    def get_market_hours(self) -> dict:
        """Get market hours info."""
        clock = self._client.get_clock()
        return {
            "is_open": clock.is_open,
            "next_open": clock.next_open,
            "next_close": clock.next_close,
        }

    def __repr__(self) -> str:
        mode = "paper" if self.paper else "live"
        return f"AlpacaBroker(mode={mode})"
