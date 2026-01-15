"""Alpaca Options trading integration."""

from datetime import datetime, date
from typing import Optional, Literal
from dataclasses import dataclass

from qwen.broker.base import (
    BrokerOrder,
    OrderSide,
    OrderType,
    OrderStatus,
    AssetClass,
)
from qwen.broker.alpaca_broker import AlpacaBroker, _convert_order_status
from qwen.config import config

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest,
        LimitOrderRequest,
        GetOrdersRequest,
    )
    from alpaca.trading.enums import (
        OrderSide as AlpacaOrderSide,
        TimeInForce,
        AssetClass as AlpacaAssetClass,
    )
    from alpaca.common.exceptions import APIError
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False


@dataclass
class AlpacaOptionContract:
    """Represents an options contract from Alpaca."""

    symbol: str  # OCC symbol (e.g., 'AAPL240216C00185000')
    underlying: str
    strike: float
    expiration: date
    option_type: str  # 'call' or 'put'
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def is_call(self) -> bool:
        return self.option_type.lower() == "call"

    @property
    def is_put(self) -> bool:
        return self.option_type.lower() == "put"


@dataclass
class OptionPosition:
    """Represents an options position."""

    symbol: str
    underlying: str
    qty: int
    avg_entry_price: float
    market_value: float
    unrealized_pl: float
    current_price: float
    strike: float
    expiration: date
    option_type: str


class AlpacaOptionsBroker:
    """
    Alpaca Options trading broker.

    Note: Alpaca Options API requires options trading to be enabled
    on your Alpaca account.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: Optional[bool] = None,
    ):
        """
        Initialize Alpaca Options broker.

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
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
                "Alpaca credentials required. Set ALPACA_API_KEY and ALPACA_SECRET_KEY."
            )

        self._client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=self.paper,
        )

        # Also create the regular broker for shared functionality
        self._stock_broker = AlpacaBroker(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=self.paper,
        )

    def get_options_chain(
        self,
        underlying: str,
        expiration: Optional[date] = None,
        option_type: Optional[Literal["call", "put"]] = None,
    ) -> list[AlpacaOptionContract]:
        """
        Get options chain for an underlying symbol.

        Args:
            underlying: Underlying symbol (e.g., 'AAPL')
            expiration: Filter by expiration date
            option_type: Filter by 'call' or 'put'

        Returns:
            List of option contracts

        Note: This is a placeholder - Alpaca's options chain API
        may have different parameters. Adjust based on actual API.
        """
        # TODO: Implement when Alpaca options API is fully available
        # The actual implementation depends on Alpaca's options data API
        raise NotImplementedError(
            "Alpaca options chain API integration pending. "
            "Use YahooDataProvider for options chain data for now."
        )

    def get_option_positions(self) -> list[OptionPosition]:
        """Get all options positions."""
        all_positions = self._stock_broker.get_positions()
        option_positions = []

        for pos in all_positions:
            if pos.asset_class == AssetClass.OPTION:
                # Parse OCC symbol to extract details
                parsed = self._parse_occ_symbol(pos.symbol)
                if parsed:
                    option_positions.append(OptionPosition(
                        symbol=pos.symbol,
                        underlying=parsed["underlying"],
                        qty=int(pos.qty),
                        avg_entry_price=pos.avg_entry_price,
                        market_value=pos.market_value,
                        unrealized_pl=pos.unrealized_pl,
                        current_price=pos.current_price,
                        strike=parsed["strike"],
                        expiration=parsed["expiration"],
                        option_type=parsed["option_type"],
                    ))

        return option_positions

    def _parse_occ_symbol(self, symbol: str) -> Optional[dict]:
        """
        Parse OCC option symbol.

        OCC format: AAPL240216C00185000
        - AAPL: underlying (1-6 chars)
        - 240216: expiration YYMMDD
        - C: call (C) or put (P)
        - 00185000: strike * 1000 (185.00)
        """
        try:
            # Find where the date starts (6 digits)
            for i in range(1, 7):
                if symbol[i:i+6].isdigit():
                    underlying = symbol[:i]
                    date_str = symbol[i:i+6]
                    option_type = "call" if symbol[i+6] == "C" else "put"
                    strike = int(symbol[i+7:]) / 1000

                    exp_date = datetime.strptime(date_str, "%y%m%d").date()

                    return {
                        "underlying": underlying,
                        "expiration": exp_date,
                        "option_type": option_type,
                        "strike": strike,
                    }
            return None
        except (ValueError, IndexError):
            return None

    def buy_option(
        self,
        symbol: str,
        qty: int,
        order_type: Literal["market", "limit"] = "market",
        limit_price: Optional[float] = None,
    ) -> BrokerOrder:
        """
        Buy an options contract.

        Args:
            symbol: OCC option symbol
            qty: Number of contracts
            order_type: 'market' or 'limit'
            limit_price: Limit price (required for limit orders)
        """
        return self._stock_broker.submit_order(
            symbol=symbol,
            qty=qty,
            side="buy",
            order_type=order_type,
            limit_price=limit_price,
        )

    def sell_option(
        self,
        symbol: str,
        qty: int,
        order_type: Literal["market", "limit"] = "market",
        limit_price: Optional[float] = None,
    ) -> BrokerOrder:
        """
        Sell an options contract.

        Args:
            symbol: OCC option symbol
            qty: Number of contracts
            order_type: 'market' or 'limit'
            limit_price: Limit price (required for limit orders)
        """
        return self._stock_broker.submit_order(
            symbol=symbol,
            qty=qty,
            side="sell",
            order_type=order_type,
            limit_price=limit_price,
        )

    def close_option_position(self, symbol: str) -> Optional[BrokerOrder]:
        """Close an options position."""
        return self._stock_broker.close_position(symbol)

    def get_account(self):
        """Get account info (delegated to stock broker)."""
        return self._stock_broker.get_account()

    def __repr__(self) -> str:
        mode = "paper" if self.paper else "live"
        return f"AlpacaOptionsBroker(mode={mode})"
