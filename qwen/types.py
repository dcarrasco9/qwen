"""
Unified type definitions for Qwen.

This module provides canonical enum types used across the codebase.
Import from here to ensure consistency between broker and paper trading modules.
"""

from enum import Enum


class OrderSide(Enum):
    """Side of an order (buy or sell)."""

    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Type of order execution."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(Enum):
    """Status of an order in its lifecycle."""

    NEW = "new"
    PENDING = "pending_new"
    ACCEPTED = "accepted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELED = "canceled"
    CANCELLED = "cancelled"  # Alias for compatibility
    EXPIRED = "expired"
    REJECTED = "rejected"


class AssetClass(Enum):
    """Asset class for securities."""

    STOCK = "us_equity"
    CRYPTO = "crypto"
    OPTION = "us_option"


# Type aliases for convenience
Side = OrderSide
Status = OrderStatus
