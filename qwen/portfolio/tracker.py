"""
Portfolio Tracking

Track positions, P&L, and performance over time.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal
import pandas as pd
import json


@dataclass
class Position:
    """A single position in the portfolio."""

    symbol: str
    quantity: float
    avg_cost: float
    position_type: Literal["stock", "option", "etf", "crypto"]
    opened_date: datetime
    notes: str = ""

    # For options
    strike: Optional[float] = None
    expiration: Optional[datetime] = None
    option_type: Optional[str] = None  # 'call' or 'put'

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_cost

    def current_value(self, current_price: float) -> float:
        return self.quantity * current_price

    def pnl(self, current_price: float) -> float:
        return self.current_value(current_price) - self.cost_basis

    def pnl_pct(self, current_price: float) -> float:
        if self.cost_basis == 0:
            return 0
        return self.pnl(current_price) / self.cost_basis * 100


@dataclass
class Trade:
    """A completed trade."""

    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    timestamp: datetime
    trade_type: Literal["stock", "option", "etf"]
    strategy: str = ""
    notes: str = ""

    # For options
    strike: Optional[float] = None
    expiration: Optional[datetime] = None

    @property
    def value(self) -> float:
        return self.quantity * self.price


class PortfolioTracker:
    """
    Track portfolio positions and performance.

    Features:
    - Position tracking
    - Trade logging
    - P&L calculation
    - Performance analytics
    """

    def __init__(self, initial_cash: float = 0):
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.created_at = datetime.now()

    def add_position(self, position: Position):
        """Add or update a position."""
        key = self._position_key(position)
        if key in self.positions:
            # Average in
            existing = self.positions[key]
            total_qty = existing.quantity + position.quantity
            total_cost = (existing.cost_basis + position.cost_basis)
            existing.quantity = total_qty
            existing.avg_cost = total_cost / total_qty if total_qty > 0 else 0
        else:
            self.positions[key] = position

    def close_position(
        self,
        symbol: str,
        quantity: float,
        price: float,
        strike: float = None,
    ) -> float:
        """
        Close (part of) a position.

        Returns realized P&L.
        """
        key = f"{symbol}_{strike}" if strike else symbol

        if key not in self.positions:
            raise ValueError(f"No position found for {key}")

        position = self.positions[key]

        if quantity > position.quantity:
            raise ValueError(f"Cannot close {quantity}, only have {position.quantity}")

        # Calculate realized P&L
        cost_per_share = position.avg_cost
        realized_pnl = (price - cost_per_share) * quantity

        # Reduce position
        position.quantity -= quantity

        if position.quantity <= 0:
            del self.positions[key]

        # Add cash
        self.cash += quantity * price

        # Log trade
        self.trades.append(Trade(
            symbol=symbol,
            side="sell",
            quantity=quantity,
            price=price,
            timestamp=datetime.now(),
            trade_type=position.position_type,
            strike=strike,
        ))

        return realized_pnl

    def _position_key(self, position: Position) -> str:
        """Generate unique key for position."""
        if position.strike:
            return f"{position.symbol}_{position.strike}"
        return position.symbol

    def get_positions_df(self, prices: dict[str, float] = None) -> pd.DataFrame:
        """
        Get positions as DataFrame.

        Args:
            prices: Dict of symbol -> current price for P&L calc
        """
        if not self.positions:
            return pd.DataFrame()

        data = []
        for key, pos in self.positions.items():
            current_price = prices.get(pos.symbol, pos.avg_cost) if prices else pos.avg_cost

            data.append({
                "symbol": pos.symbol,
                "type": pos.position_type,
                "quantity": pos.quantity,
                "avg_cost": pos.avg_cost,
                "cost_basis": pos.cost_basis,
                "current_price": current_price,
                "current_value": pos.current_value(current_price),
                "pnl": pos.pnl(current_price),
                "pnl_pct": pos.pnl_pct(current_price),
                "strike": pos.strike,
                "expiration": pos.expiration,
            })

        return pd.DataFrame(data)

    def get_trades_df(self) -> pd.DataFrame:
        """Get trade history as DataFrame."""
        if not self.trades:
            return pd.DataFrame()

        return pd.DataFrame([
            {
                "timestamp": t.timestamp,
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "value": t.value,
                "type": t.trade_type,
                "strategy": t.strategy,
            }
            for t in self.trades
        ])

    def get_summary(self, prices: dict[str, float] = None) -> dict:
        """
        Get portfolio summary.

        Args:
            prices: Current prices for P&L calculation
        """
        positions_df = self.get_positions_df(prices)

        if positions_df.empty:
            return {
                "total_value": self.cash,
                "cash": self.cash,
                "positions_value": 0,
                "total_pnl": 0,
                "total_pnl_pct": 0,
                "num_positions": 0,
            }

        positions_value = positions_df["current_value"].sum()
        total_pnl = positions_df["pnl"].sum()
        total_cost = positions_df["cost_basis"].sum()

        return {
            "total_value": self.cash + positions_value,
            "cash": self.cash,
            "positions_value": positions_value,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl / total_cost * 100 if total_cost > 0 else 0,
            "num_positions": len(self.positions),
            "winning_positions": len(positions_df[positions_df["pnl"] > 0]),
            "losing_positions": len(positions_df[positions_df["pnl"] < 0]),
        }

    def save(self, filepath: str):
        """Save portfolio to JSON file."""
        data = {
            "cash": self.cash,
            "created_at": self.created_at.isoformat(),
            "positions": [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "avg_cost": p.avg_cost,
                    "position_type": p.position_type,
                    "opened_date": p.opened_date.isoformat(),
                    "strike": p.strike,
                    "expiration": p.expiration.isoformat() if p.expiration else None,
                    "option_type": p.option_type,
                    "notes": p.notes,
                }
                for p in self.positions.values()
            ],
            "trades": [
                {
                    "symbol": t.symbol,
                    "side": t.side,
                    "quantity": t.quantity,
                    "price": t.price,
                    "timestamp": t.timestamp.isoformat(),
                    "trade_type": t.trade_type,
                    "strategy": t.strategy,
                    "strike": t.strike,
                }
                for t in self.trades
            ],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "PortfolioTracker":
        """Load portfolio from JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)

        tracker = cls(initial_cash=data["cash"])
        tracker.created_at = datetime.fromisoformat(data["created_at"])

        for p in data["positions"]:
            tracker.positions[p["symbol"]] = Position(
                symbol=p["symbol"],
                quantity=p["quantity"],
                avg_cost=p["avg_cost"],
                position_type=p["position_type"],
                opened_date=datetime.fromisoformat(p["opened_date"]),
                strike=p.get("strike"),
                expiration=datetime.fromisoformat(p["expiration"]) if p.get("expiration") else None,
                option_type=p.get("option_type"),
                notes=p.get("notes", ""),
            )

        for t in data["trades"]:
            tracker.trades.append(Trade(
                symbol=t["symbol"],
                side=t["side"],
                quantity=t["quantity"],
                price=t["price"],
                timestamp=datetime.fromisoformat(t["timestamp"]),
                trade_type=t["trade_type"],
                strategy=t.get("strategy", ""),
                strike=t.get("strike"),
            ))

        return tracker
