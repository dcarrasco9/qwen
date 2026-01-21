"""
Configuration management for Qwen.

This module provides the core configuration system for Qwen. Configuration is loaded
from environment variables with support for .env files.

Configuration Hierarchy
-----------------------
1. qwen.config.Config - Core application config (API keys, defaults)
2. qwen.wheel.config.WheelConfig - Strategy-specific config (loaded from YAML)

Usage
-----
For most cases, use the global config singleton:

    from qwen.config import config
    api_key = config.alpaca_api_key

For testing or custom configurations, use the factory function:

    from qwen.config import get_config
    custom_config = get_config(alpaca_paper=True)

For strategy-specific configs (wheel strategy), see qwen.wheel.config:

    from qwen.wheel.config import load_config
    wheel_config = load_config("wheel_config.yaml")
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

# Load .env file from project root
from dotenv import load_dotenv

# Find and load .env file
_project_root = Path(__file__).parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    # Also check current working directory
    load_dotenv()


@dataclass
class Config:
    """
    Application configuration loaded from environment variables.

    Attributes:
        alpaca_api_key: Alpaca Markets API key
        alpaca_secret_key: Alpaca Markets secret key
        alpaca_paper: Whether to use Alpaca paper trading (default: True)
        schwab_api_key: Schwab/TDA API key
        schwab_api_secret: Schwab/TDA API secret
        schwab_callback_url: OAuth callback URL for Schwab
        default_risk_free_rate: Default risk-free rate for options pricing
        default_slippage: Default slippage for paper trading
        default_commission: Default commission per trade
        paper_starting_balance: Starting balance for paper trading
        market_timezone: Market timezone (default: America/New_York)
        local_timezone: Local timezone for display
    """

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

    # Timezone settings - market operates in Eastern Time
    market_timezone: str = field(default_factory=lambda: os.getenv("MARKET_TIMEZONE", "America/New_York"))
    local_timezone: str = field(default_factory=lambda: os.getenv("LOCAL_TIMEZONE", "America/Los_Angeles"))

    @property
    def market_tz(self) -> ZoneInfo:
        """Get market timezone (Eastern Time)."""
        return ZoneInfo(self.market_timezone)

    @property
    def local_tz(self) -> ZoneInfo:
        """Get local timezone."""
        return ZoneInfo(self.local_timezone)

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


class ConfigManager:
    """
    Unified configuration manager for accessing all Qwen configs.

    This class provides a centralized way to access both core application
    configuration and strategy-specific configurations.

    Example:
        manager = ConfigManager()

        # Access core config
        if manager.config.has_alpaca_credentials:
            api_key = manager.config.alpaca_api_key

        # Access wheel config (loaded on demand)
        wheel_cfg = manager.get_wheel_config()
        for symbol in wheel_cfg.symbols:
            print(symbol.symbol)
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the config manager.

        Args:
            config: Optional custom Config instance. If None, uses default.
        """
        self._config = config or Config.from_env()
        self._wheel_config = None

    @property
    def config(self) -> Config:
        """Get the core application configuration."""
        return self._config

    def get_wheel_config(self, config_path: Optional[Path] = None):
        """
        Get wheel strategy configuration.

        Lazily loads wheel config from YAML on first access.

        Args:
            config_path: Optional path to YAML config file.
                        If None, uses default search paths.

        Returns:
            WheelConfig object

        Raises:
            ImportError: If wheel.config module cannot be imported
        """
        if self._wheel_config is None or config_path is not None:
            from qwen.wheel.config import load_config
            self._wheel_config = load_config(config_path)
        return self._wheel_config

    def reload(self) -> None:
        """Reload all configurations from their sources."""
        self._config = Config.from_env()
        self._wheel_config = None

    def __repr__(self) -> str:
        has_alpaca = "yes" if self._config.has_alpaca_credentials else "no"
        has_schwab = "yes" if self._config.has_schwab_credentials else "no"
        paper = "paper" if self._config.alpaca_paper else "live"
        return f"ConfigManager(alpaca={has_alpaca}/{paper}, schwab={has_schwab})"


def get_config(**overrides) -> Config:
    """
    Factory function to create a Config instance with optional overrides.

    This is useful for testing or creating custom configurations without
    modifying the global config singleton.

    Args:
        **overrides: Keyword arguments to override default config values.

    Returns:
        Config instance with the specified overrides.

    Example:
        # Create a test config with paper trading disabled
        test_config = get_config(alpaca_paper=False, default_slippage=0.002)
    """
    base_config = Config.from_env()

    for key, value in overrides.items():
        if hasattr(base_config, key):
            setattr(base_config, key, value)
        else:
            raise ValueError(f"Unknown config attribute: {key}")

    return base_config


# Global config instance (backward compatible)
config = Config.from_env()

# Global config manager instance
config_manager = ConfigManager(config)
