"""Performance metrics for backtesting."""

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""

    # Returns
    total_return: float
    annualized_return: float
    volatility: float

    # Risk-adjusted
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Drawdown
    max_drawdown: float
    max_drawdown_duration: int  # in periods

    # Trade statistics
    num_trades: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float

    # Other
    exposure_time: float  # Percent of time in market

    @classmethod
    def from_equity_curve(
        cls,
        equity: pd.Series,
        trades: pd.DataFrame = None,
        risk_free_rate: float = 0.05,
        periods_per_year: int = 252,
    ) -> "PerformanceMetrics":
        """
        Calculate metrics from equity curve and trades.

        Args:
            equity: Time series of portfolio equity
            trades: DataFrame of trades with 'side', 'quantity', 'price', 'pnl' columns
            risk_free_rate: Annual risk-free rate
            periods_per_year: Trading periods per year (252 for daily)

        Returns:
            PerformanceMetrics instance
        """
        if len(equity) < 2:
            return cls._empty_metrics()

        returns = equity.pct_change().dropna()

        # Basic return metrics
        total_return = (equity.iloc[-1] / equity.iloc[0]) - 1
        n_periods = len(returns)

        annualized_return = (1 + total_return) ** (periods_per_year / n_periods) - 1
        volatility = returns.std() * np.sqrt(periods_per_year)

        # Sharpe ratio
        excess_return = annualized_return - risk_free_rate
        sharpe = excess_return / volatility if volatility > 0 else 0

        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(periods_per_year) if len(downside_returns) > 0 else 0
        sortino = excess_return / downside_std if downside_std > 0 else 0

        # Drawdown calculations
        rolling_max = equity.expanding().max()
        drawdown = (equity - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        # Max drawdown duration
        is_underwater = drawdown < 0
        underwater_periods = []
        current_duration = 0
        for underwater in is_underwater:
            if underwater:
                current_duration += 1
            else:
                if current_duration > 0:
                    underwater_periods.append(current_duration)
                current_duration = 0
        if current_duration > 0:
            underwater_periods.append(current_duration)
        max_dd_duration = max(underwater_periods) if underwater_periods else 0

        # Calmar ratio
        calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # Trade statistics
        trade_stats = cls._calculate_trade_stats(trades)

        # Exposure time
        exposure = (equity != equity.shift(1)).sum() / len(equity) if len(equity) > 0 else 0

        return cls(
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_dd_duration,
            num_trades=trade_stats["num_trades"],
            win_rate=trade_stats["win_rate"],
            profit_factor=trade_stats["profit_factor"],
            avg_win=trade_stats["avg_win"],
            avg_loss=trade_stats["avg_loss"],
            largest_win=trade_stats["largest_win"],
            largest_loss=trade_stats["largest_loss"],
            exposure_time=exposure,
        )

    @classmethod
    def _calculate_trade_stats(cls, trades: Optional[pd.DataFrame]) -> dict:
        """Calculate trade-level statistics."""
        default_stats = {
            "num_trades": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "largest_win": 0,
            "largest_loss": 0,
        }

        if trades is None or len(trades) == 0:
            return default_stats

        # Calculate P&L per trade if not present
        if "pnl" not in trades.columns:
            # Calculate P&L from buy/sell pairs
            pnls = []
            buy_cost = 0
            buy_qty = 0

            for _, trade in trades.iterrows():
                if trade["side"] == "buy":
                    buy_cost += trade["quantity"] * trade["price"]
                    buy_qty += trade["quantity"]
                elif trade["side"] == "sell" and buy_qty > 0:
                    sell_qty = min(trade["quantity"], buy_qty)
                    avg_buy_price = buy_cost / buy_qty if buy_qty > 0 else 0
                    pnl = sell_qty * (trade["price"] - avg_buy_price)
                    pnls.append(pnl)
                    buy_qty -= sell_qty
                    buy_cost = buy_qty * avg_buy_price

            if not pnls:
                return {**default_stats, "num_trades": len(trades)}

            pnls = pd.Series(pnls)
        else:
            pnls = trades["pnl"]
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]

        num_trades = len(pnls)
        win_rate = len(wins) / num_trades if num_trades > 0 else 0

        gross_profit = wins.sum() if len(wins) > 0 else 0
        gross_loss = abs(losses.sum()) if len(losses) > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

        return {
            "num_trades": num_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win": wins.mean() if len(wins) > 0 else 0,
            "avg_loss": losses.mean() if len(losses) > 0 else 0,
            "largest_win": wins.max() if len(wins) > 0 else 0,
            "largest_loss": losses.min() if len(losses) > 0 else 0,
        }

    @classmethod
    def _empty_metrics(cls) -> "PerformanceMetrics":
        """Return empty metrics."""
        return cls(
            total_return=0,
            annualized_return=0,
            volatility=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            calmar_ratio=0,
            max_drawdown=0,
            max_drawdown_duration=0,
            num_trades=0,
            win_rate=0,
            profit_factor=0,
            avg_win=0,
            avg_loss=0,
            largest_win=0,
            largest_loss=0,
            exposure_time=0,
        )

    def summary(self) -> dict:
        """Return metrics as dictionary."""
        return {
            "Total Return": f"{self.total_return:.2%}",
            "Annualized Return": f"{self.annualized_return:.2%}",
            "Volatility": f"{self.volatility:.2%}",
            "Sharpe Ratio": f"{self.sharpe_ratio:.2f}",
            "Sortino Ratio": f"{self.sortino_ratio:.2f}",
            "Calmar Ratio": f"{self.calmar_ratio:.2f}",
            "Max Drawdown": f"{self.max_drawdown:.2%}",
            "Max DD Duration": f"{self.max_drawdown_duration} periods",
            "Number of Trades": self.num_trades,
            "Win Rate": f"{self.win_rate:.2%}",
            "Profit Factor": f"{self.profit_factor:.2f}",
            "Avg Win": f"${self.avg_win:.2f}",
            "Avg Loss": f"${self.avg_loss:.2f}",
        }

    def __str__(self) -> str:
        """String representation of metrics."""
        lines = ["=" * 40, "Performance Metrics", "=" * 40]
        for key, value in self.summary().items():
            lines.append(f"{key:.<25} {value}")
        return "\n".join(lines)


def calculate_sharpe(returns: pd.Series, risk_free_rate: float = 0.05, periods_per_year: int = 252) -> float:
    """
    Calculate Sharpe ratio.

    Args:
        returns: Series of periodic returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Periods per year

    Returns:
        Sharpe ratio
    """
    if len(returns) == 0:
        return 0

    excess_returns = returns - risk_free_rate / periods_per_year
    if excess_returns.std() == 0:
        return 0
    return np.sqrt(periods_per_year) * excess_returns.mean() / excess_returns.std()


def calculate_sortino(returns: pd.Series, risk_free_rate: float = 0.05, periods_per_year: int = 252) -> float:
    """
    Calculate Sortino ratio (downside risk-adjusted return).

    Args:
        returns: Series of periodic returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Periods per year

    Returns:
        Sortino ratio
    """
    if len(returns) == 0:
        return 0

    excess_returns = returns - risk_free_rate / periods_per_year
    downside_returns = returns[returns < 0]

    if len(downside_returns) == 0 or downside_returns.std() == 0:
        return float("inf") if excess_returns.mean() > 0 else 0

    downside_std = downside_returns.std()
    return np.sqrt(periods_per_year) * excess_returns.mean() / downside_std


def calculate_max_drawdown(equity: pd.Series) -> tuple[float, int, int]:
    """
    Calculate maximum drawdown and its location.

    Args:
        equity: Equity time series

    Returns:
        Tuple of (max_drawdown, peak_idx, trough_idx)
    """
    rolling_max = equity.expanding().max()
    drawdown = (equity - rolling_max) / rolling_max

    trough_idx = drawdown.idxmin()
    peak_idx = equity[:trough_idx].idxmax() if isinstance(trough_idx, (int, np.integer)) else equity.loc[:trough_idx].idxmax()

    return drawdown.min(), peak_idx, trough_idx
