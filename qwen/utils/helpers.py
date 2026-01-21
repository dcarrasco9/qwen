"""Helper functions for financial calculations."""

import numpy as np
import pandas as pd
from typing import Union


def safe_float(val, default: float = 0.0) -> float:
    """
    Safely convert a value to float, handling NaN and None.

    Args:
        val: Value to convert
        default: Default value if conversion fails

    Returns:
        Float value or default
    """
    if val is None:
        return default
    if pd.isna(val):
        return default
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default


def safe_int(val, default: int = 0) -> int:
    """
    Safely convert a value to int, handling NaN and None.

    Args:
        val: Value to convert
        default: Default value if conversion fails

    Returns:
        Int value or default
    """
    if val is None:
        return default
    if pd.isna(val):
        return default
    try:
        return int(val) if val else default
    except (ValueError, TypeError):
        return default


def annualize_returns(returns: Union[pd.Series, np.ndarray], periods_per_year: int = 252) -> float:
    """
    Annualize returns from a series of periodic returns.

    Args:
        returns: Series of periodic returns
        periods_per_year: Number of periods in a year (252 for daily, 52 for weekly, 12 for monthly)

    Returns:
        Annualized return as a decimal
    """
    total_return = (1 + returns).prod()
    n_periods = len(returns)
    return total_return ** (periods_per_year / n_periods) - 1


def calculate_volatility(returns: Union[pd.Series, np.ndarray], periods_per_year: int = 252) -> float:
    """
    Calculate annualized volatility from returns.

    Args:
        returns: Series of periodic returns
        periods_per_year: Number of periods in a year

    Returns:
        Annualized volatility (standard deviation)
    """
    return np.std(returns, ddof=1) * np.sqrt(periods_per_year)


def calculate_drawdown(equity_curve: Union[pd.Series, np.ndarray]) -> pd.Series:
    """
    Calculate drawdown series from an equity curve.

    Args:
        equity_curve: Series of portfolio values over time

    Returns:
        Series of drawdown percentages (negative values)
    """
    if isinstance(equity_curve, np.ndarray):
        equity_curve = pd.Series(equity_curve)

    rolling_max = equity_curve.expanding().max()
    drawdown = (equity_curve - rolling_max) / rolling_max
    return drawdown


def calculate_max_drawdown(equity_curve: Union[pd.Series, np.ndarray]) -> float:
    """
    Calculate maximum drawdown from an equity curve.

    Args:
        equity_curve: Series of portfolio values over time

    Returns:
        Maximum drawdown as a decimal (negative value)
    """
    return calculate_drawdown(equity_curve).min()
