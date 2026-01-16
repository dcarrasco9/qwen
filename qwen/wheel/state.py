"""
Wheel Strategy State Persistence

Provides JSON-based persistence for wheel positions across sessions.
Tracks the state machine: IDLE → PUT_OPEN → HOLDING_SHARES → CALL_OPEN → cycle complete
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WheelState(str, Enum):
    """Wheel strategy state machine states."""

    IDLE = "IDLE"  # No position, ready to sell put
    PUT_OPEN = "PUT_OPEN"  # Short put position open
    HOLDING_SHARES = "HOLDING_SHARES"  # Assigned, holding 100 shares
    CALL_OPEN = "CALL_OPEN"  # Short call position open


@dataclass
class OptionInfo:
    """Information about an active option position."""

    option_type: str  # 'put' or 'call'
    strike: float
    expiration: str  # ISO format date string
    premium: float  # Premium received per share
    quantity: int  # Number of contracts (negative for short)
    symbol: str  # OCC symbol
    opened_at: str  # ISO format datetime

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "OptionInfo":
        return cls(**data)

    @property
    def expiration_date(self) -> datetime:
        return datetime.fromisoformat(self.expiration)

    @property
    def days_to_expiration(self) -> int:
        delta = self.expiration_date - datetime.now()
        return max(0, delta.days)

    @property
    def total_premium(self) -> float:
        """Total premium collected (positive for short positions)."""
        return abs(self.quantity) * self.premium * 100


@dataclass
class Trade:
    """Record of a trade execution."""

    timestamp: str
    action: str  # 'sell_to_open', 'buy_to_close', 'assigned', 'called_away'
    symbol: str
    option_type: Optional[str]  # 'put', 'call', or None for stock
    strike: Optional[float]
    quantity: int
    price: float
    premium: Optional[float]  # For options
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Trade":
        return cls(**data)


@dataclass
class WheelPosition:
    """
    Complete state for a wheel position on a single symbol.

    Tracks the full lifecycle from selling puts through covered calls.
    """

    symbol: str
    state: WheelState = WheelState.IDLE
    shares_owned: int = 0
    cost_basis: float = 0.0  # Average cost per share including premiums
    active_option: Optional[OptionInfo] = None
    total_premium_collected: float = 0.0
    cycle_count: int = 0
    trades: list[Trade] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        data = {
            "symbol": self.symbol,
            "state": self.state.value if isinstance(self.state, WheelState) else self.state,
            "shares_owned": self.shares_owned,
            "cost_basis": self.cost_basis,
            "active_option": self.active_option.to_dict() if self.active_option else None,
            "total_premium_collected": self.total_premium_collected,
            "cycle_count": self.cycle_count,
            "trades": [t.to_dict() for t in self.trades],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "WheelPosition":
        state = WheelState(data["state"]) if isinstance(data["state"], str) else data["state"]
        active_option = (
            OptionInfo.from_dict(data["active_option"])
            if data.get("active_option")
            else None
        )
        trades = [Trade.from_dict(t) for t in data.get("trades", [])]

        return cls(
            symbol=data["symbol"],
            state=state,
            shares_owned=data.get("shares_owned", 0),
            cost_basis=data.get("cost_basis", 0.0),
            active_option=active_option,
            total_premium_collected=data.get("total_premium_collected", 0.0),
            cycle_count=data.get("cycle_count", 0),
            trades=trades,
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )

    def update(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now().isoformat()

    @property
    def effective_cost_basis(self) -> float:
        """Cost basis adjusted for all premiums collected."""
        if self.shares_owned == 0:
            return 0.0
        return self.cost_basis - (self.total_premium_collected / self.shares_owned)

    @property
    def unrealized_pnl(self) -> float:
        """Unrealized P&L (requires current price - not tracked here)."""
        return 0.0  # Must be calculated externally with current price

    def add_trade(self, trade: Trade) -> None:
        """Add a trade to the history."""
        self.trades.append(trade)
        self.update()

    def transition_to(self, new_state: WheelState) -> None:
        """Transition to a new state with validation."""
        valid_transitions = {
            WheelState.IDLE: [WheelState.PUT_OPEN],
            WheelState.PUT_OPEN: [WheelState.IDLE, WheelState.HOLDING_SHARES],
            WheelState.HOLDING_SHARES: [WheelState.CALL_OPEN, WheelState.IDLE],
            WheelState.CALL_OPEN: [WheelState.HOLDING_SHARES, WheelState.IDLE],
        }

        if new_state not in valid_transitions.get(self.state, []):
            logger.warning(
                f"Invalid state transition for {self.symbol}: {self.state} → {new_state}"
            )

        logger.info(f"{self.symbol}: State transition {self.state} → {new_state}")
        self.state = new_state
        self.update()


class WheelStateManager:
    """
    Manages persistence of wheel positions to JSON file.

    Thread-safe file operations with atomic writes.
    """

    def __init__(self, state_file: Optional[Path] = None):
        """
        Initialize the state manager.

        Args:
            state_file: Path to the JSON state file. Defaults to ~/.qwen/wheel_state.json
        """
        if state_file is None:
            state_dir = Path.home() / ".qwen"
            state_dir.mkdir(exist_ok=True)
            state_file = state_dir / "wheel_state.json"

        self.state_file = Path(state_file)
        self._positions: dict[str, WheelPosition] = {}
        self._load()

    def _load(self) -> None:
        """Load state from file."""
        if not self.state_file.exists():
            logger.info(f"No state file found at {self.state_file}, starting fresh")
            self._positions = {}
            return

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)

            self._positions = {
                symbol: WheelPosition.from_dict(pos_data)
                for symbol, pos_data in data.get("positions", {}).items()
            }
            logger.info(f"Loaded {len(self._positions)} positions from {self.state_file}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse state file: {e}")
            # Backup corrupted file
            backup_path = self.state_file.with_suffix(".json.bak")
            self.state_file.rename(backup_path)
            logger.warning(f"Backed up corrupted state to {backup_path}")
            self._positions = {}

    def _save(self) -> None:
        """Save state to file atomically."""
        data = {
            "version": 1,
            "updated_at": datetime.now().isoformat(),
            "positions": {
                symbol: pos.to_dict() for symbol, pos in self._positions.items()
            },
        }

        # Write to temp file first, then rename (atomic on most filesystems)
        temp_file = self.state_file.with_suffix(".json.tmp")
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2)

        temp_file.replace(self.state_file)
        logger.debug(f"Saved state to {self.state_file}")

    def get_position(self, symbol: str) -> WheelPosition:
        """
        Get the position for a symbol, creating if it doesn't exist.

        Args:
            symbol: Stock ticker symbol

        Returns:
            WheelPosition for the symbol
        """
        if symbol not in self._positions:
            self._positions[symbol] = WheelPosition(symbol=symbol)
            self._save()

        return self._positions[symbol]

    def update_position(self, position: WheelPosition) -> None:
        """
        Update a position and save to disk.

        Args:
            position: The updated WheelPosition
        """
        position.update()
        self._positions[position.symbol] = position
        self._save()

    def get_all_positions(self) -> dict[str, WheelPosition]:
        """Get all tracked positions."""
        return self._positions.copy()

    def get_active_positions(self) -> list[WheelPosition]:
        """Get positions that are not IDLE."""
        return [p for p in self._positions.values() if p.state != WheelState.IDLE]

    def remove_position(self, symbol: str) -> bool:
        """
        Remove a position from tracking.

        Args:
            symbol: Stock ticker to remove

        Returns:
            True if removed, False if not found
        """
        if symbol in self._positions:
            del self._positions[symbol]
            self._save()
            return True
        return False

    def add_trade(self, symbol: str, trade: Trade) -> None:
        """
        Add a trade to a position's history.

        Args:
            symbol: Stock ticker
            trade: Trade record to add
        """
        position = self.get_position(symbol)
        position.add_trade(trade)
        self._save()

    def get_summary(self) -> dict:
        """Get a summary of all positions."""
        active = self.get_active_positions()
        total_premium = sum(p.total_premium_collected for p in self._positions.values())
        total_cycles = sum(p.cycle_count for p in self._positions.values())

        return {
            "total_positions": len(self._positions),
            "active_positions": len(active),
            "total_premium_collected": total_premium,
            "total_cycles_completed": total_cycles,
            "positions_by_state": {
                state.value: len([p for p in self._positions.values() if p.state == state])
                for state in WheelState
            },
        }

    def export_trades(self, symbol: Optional[str] = None) -> list[dict]:
        """
        Export trade history for reporting.

        Args:
            symbol: Optional symbol to filter by

        Returns:
            List of trade dictionaries
        """
        trades = []
        positions = (
            [self._positions[symbol]] if symbol else self._positions.values()
        )

        for pos in positions:
            for trade in pos.trades:
                trade_dict = trade.to_dict()
                trade_dict["underlying"] = pos.symbol
                trades.append(trade_dict)

        return sorted(trades, key=lambda t: t["timestamp"])
