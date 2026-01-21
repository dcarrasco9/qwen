"""
Factory functions for creating data provider instances.

This module provides a unified way to create data provider instances based on
configuration and available dependencies.
"""

from typing import Literal, Optional

from qwen.config import config
from qwen.data.base import DataProvider


DataProviderType = Literal["yahoo", "alpaca", "schwab"]


def create_data_provider(
    provider_type: DataProviderType = "yahoo",
    **kwargs
) -> DataProvider:
    """
    Create a data provider instance based on type and configuration.

    Args:
        provider_type: Type of provider to create:
            - "yahoo": Yahoo Finance (free, no API key required)
            - "alpaca": Alpaca Markets (requires API key)
            - "schwab": Schwab (requires API key, NOT FULLY IMPLEMENTED)
        **kwargs: Additional arguments passed to provider constructor.

    Returns:
        DataProvider instance

    Raises:
        ImportError: If required dependencies are not installed
        ValueError: If provider type is unknown or credentials are missing

    Example:
        # Create Yahoo Finance provider (default, no credentials needed)
        provider = create_data_provider("yahoo")

        # Create Alpaca provider (uses credentials from config)
        provider = create_data_provider("alpaca")
    """
    if provider_type == "yahoo":
        return _create_yahoo_provider(**kwargs)
    elif provider_type == "alpaca":
        return _create_alpaca_provider(**kwargs)
    elif provider_type == "schwab":
        return _create_schwab_provider(**kwargs)
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")


def _create_yahoo_provider(**kwargs) -> DataProvider:
    """Create Yahoo Finance data provider."""
    from qwen.data.yahoo import YahooDataProvider
    return YahooDataProvider()


def _create_alpaca_provider(**kwargs) -> DataProvider:
    """Create Alpaca data provider."""
    try:
        from qwen.data.alpaca import AlpacaDataProvider
    except ImportError as e:
        raise ImportError(
            "AlpacaDataProvider requires alpaca-py. Install with: pip install alpaca-py"
        ) from e

    if not config.has_alpaca_credentials:
        raise ValueError(
            "Alpaca credentials required. Set ALPACA_API_KEY and ALPACA_SECRET_KEY."
        )

    return AlpacaDataProvider(
        api_key=kwargs.get("api_key", config.alpaca_api_key),
        secret_key=kwargs.get("secret_key", config.alpaca_secret_key),
        paper=kwargs.get("paper", config.alpaca_paper),
    )


def _create_schwab_provider(**kwargs) -> DataProvider:
    """Create Schwab data provider."""
    try:
        from qwen.data.schwab import SchwabDataProvider
    except ImportError as e:
        raise ImportError(
            "SchwabDataProvider requires schwab-py. Install with: pip install schwab-py"
        ) from e

    if not config.has_schwab_credentials:
        raise ValueError(
            "Schwab credentials required. Set SCHWAB_API_KEY and SCHWAB_API_SECRET."
        )

    return SchwabDataProvider(
        api_key=kwargs.get("api_key", config.schwab_api_key),
        api_secret=kwargs.get("api_secret", config.schwab_api_secret),
        callback_url=kwargs.get("callback_url", config.schwab_callback_url),
    )


def get_available_providers() -> list[str]:
    """
    Get list of available data provider types based on installed dependencies.

    Returns:
        List of available provider type strings
    """
    available = ["yahoo"]  # Yahoo is always available (uses yfinance)

    try:
        import alpaca
        if config.has_alpaca_credentials:
            available.append("alpaca")
    except ImportError:
        pass

    try:
        import schwab
        if config.has_schwab_credentials:
            available.append("schwab")
    except ImportError:
        pass

    return available


def get_default_provider() -> DataProvider:
    """
    Get the best available data provider based on installed dependencies.

    Priority order:
    1. Alpaca (if credentials available)
    2. Yahoo Finance (fallback, always available)

    Returns:
        DataProvider instance
    """
    available = get_available_providers()

    if "alpaca" in available:
        return create_data_provider("alpaca")

    return create_data_provider("yahoo")
