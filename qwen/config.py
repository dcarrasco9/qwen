"""Configuration management for Qwen."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Alpaca API
    alpaca_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ALPACA_API_KEY"))
    alpaca_secret_key: Optional[str] = field(default_factory=lambda: os.getenv("ALPACA_SECRET_KEY"))
    alpaca_paper: bool = field(default_factory=lambda: os.getenv("ALPACA_PAPER", "true").lower() == "true")

    # Schwab/TD Ameritrade API
    schwab_api_key: Optional[str] = field(default_factory=lambda: os.getenv("SCHWAB_API_KEY"))
    schwab_api_secret: Optional[str] = field(default_factory=lambda: os.getenv("SCHWAB_API_SECRET"))
    schwab_callback_url: str = field(default_factory=lambda: os.getenv("SCHWAB_CALLBACK_URL", "https://127.0.0.1"))

    # Default settings
    default_risk_free_rate: float = 0.05  # 5% default
    default_slippage: float = 0.001  # 0.1% slippage
    default_commission: float = 0.0  # Commission per trade

    # Paper trading defaults
    paper_starting_balance: float = 100_000.0

    @property
    def has_alpaca_credentials(self) -> bool:
        """Check if Alpaca API credentials are configured."""
        return bool(self.alpaca_api_key and self.alpaca_secret_key)

    @property
    def has_schwab_credentials(self) -> bool:
        """Check if Schwab API credentials are configured."""
        return bool(self.schwab_api_key and self.schwab_api_secret)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls()


# Global config instance
config = Config.from_env()
