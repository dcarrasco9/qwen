"""
Factory functions for creating broker instances.

This module provides a unified way to create broker instances based on
configuration and available dependencies.
"""

from typing import Literal, Optional

from qwen.config import config
from qwen.broker.base import BaseBroker


BrokerType = Literal["alpaca", "alpaca_options", "paper"]


def create_broker(
    broker_type: BrokerType = "alpaca",
    paper: Optional[bool] = None,
    **kwargs
) -> BaseBroker:
    """
    Create a broker instance based on type and configuration.

    Args:
        broker_type: Type of broker to create:
            - "alpaca": Alpaca stock trading broker
            - "alpaca_options": Alpaca options trading broker
            - "paper": Paper trading broker (simulated)
        paper: Whether to use paper trading. If None, uses config default.
        **kwargs: Additional arguments passed to broker constructor.

    Returns:
        BaseBroker instance

    Raises:
        ImportError: If required dependencies are not installed
        ValueError: If broker type is unknown or credentials are missing

    Example:
        # Create live Alpaca broker (uses credentials from config)
        broker = create_broker("alpaca")

        # Create paper trading broker
        broker = create_broker("alpaca", paper=True)

        # Create options broker
        options_broker = create_broker("alpaca_options")
    """
    # Determine paper trading mode
    use_paper = paper if paper is not None else config.alpaca_paper

    if broker_type == "alpaca":
        return _create_alpaca_broker(paper=use_paper, **kwargs)
    elif broker_type == "alpaca_options":
        return _create_alpaca_options_broker(paper=use_paper, **kwargs)
    elif broker_type == "paper":
        return _create_paper_broker(**kwargs)
    else:
        raise ValueError(f"Unknown broker type: {broker_type}")


def _create_alpaca_broker(paper: bool = True, **kwargs) -> BaseBroker:
    """Create Alpaca stock broker."""
    try:
        from qwen.broker.alpaca import AlpacaBroker
    except ImportError as e:
        raise ImportError(
            "AlpacaBroker requires alpaca-py. Install with: pip install alpaca-py"
        ) from e

    if not config.has_alpaca_credentials:
        raise ValueError(
            "Alpaca credentials required. Set ALPACA_API_KEY and ALPACA_SECRET_KEY."
        )

    return AlpacaBroker(
        api_key=kwargs.get("api_key", config.alpaca_api_key),
        secret_key=kwargs.get("secret_key", config.alpaca_secret_key),
        paper=paper,
    )


def _create_alpaca_options_broker(paper: bool = True, **kwargs) -> BaseBroker:
    """Create Alpaca options broker."""
    try:
        from qwen.broker.alpaca_options import AlpacaOptionsBroker
    except ImportError as e:
        raise ImportError(
            "AlpacaOptionsBroker requires alpaca-py. Install with: pip install alpaca-py"
        ) from e

    if not config.has_alpaca_credentials:
        raise ValueError(
            "Alpaca credentials required. Set ALPACA_API_KEY and ALPACA_SECRET_KEY."
        )

    return AlpacaOptionsBroker(
        api_key=kwargs.get("api_key", config.alpaca_api_key),
        secret_key=kwargs.get("secret_key", config.alpaca_secret_key),
        paper=paper,
    )


def _create_paper_broker(**kwargs):
    """Create paper trading broker."""
    from qwen.paper.broker import PaperBroker
    from qwen.paper.account import PaperAccount

    starting_balance = kwargs.get("starting_balance", config.paper_starting_balance)
    slippage = kwargs.get("slippage", config.default_slippage)
    commission = kwargs.get("commission", config.default_commission)

    account = PaperAccount(starting_balance=starting_balance)
    return PaperBroker(
        account=account,
        slippage=slippage,
        commission=commission,
        price_provider=kwargs.get("price_provider"),
    )


def get_available_brokers() -> list[str]:
    """
    Get list of available broker types based on installed dependencies.

    Returns:
        List of available broker type strings
    """
    available = ["paper"]  # Paper trading is always available

    try:
        import alpaca
        if config.has_alpaca_credentials:
            available.append("alpaca")
            available.append("alpaca_options")
    except ImportError:
        pass

    return available
