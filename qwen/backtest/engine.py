"""Backtesting engine."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import pandas as pd

from qwen.backtest.strategy import Strategy, Signal
from qwen.backtest.portfolio import Portfolio
from qwen.backtest.metrics import PerformanceMetrics


@dataclass
class BacktestResult:
    """Results from a backtest run."""

    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_equity: float
    total_return: float
    metrics: PerformanceMetrics
    equity_curve: pd.Series
    trades: pd.DataFrame
    signals: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        """Get summary of backtest results."""
        return {
            "Strategy": self.strategy_name,
            "Period": f"{self.start_date.date()} to {self.end_date.date()}",
            "Initial Capital": f"${self.initial_capital:,.2f}",
            "Final Equity": f"${self.final_equity:,.2f}",
            "Total Return": f"{self.total_return:.2%}",
            "Sharpe Ratio": f"{self.metrics.sharpe_ratio:.2f}",
            "Max Drawdown": f"{self.metrics.max_drawdown:.2%}",
            "Num Trades": self.metrics.num_trades,
            "Win Rate": f"{self.metrics.win_rate:.2%}",
        }

    def plot(self, benchmark: Optional[pd.Series] = None):
        """
        Plot equity curve.

        Args:
            benchmark: Optional benchmark to compare against
        """
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]})

        # Equity curve
        ax1 = axes[0]
        self.equity_curve.plot(ax=ax1, label=self.strategy_name, linewidth=2)

        if benchmark is not None:
            # Normalize benchmark to start at same value
            normalized_bench = benchmark / benchmark.iloc[0] * self.initial_capital
            normalized_bench.plot(ax=ax1, label="Benchmark", linewidth=1, alpha=0.7)

        ax1.set_ylabel("Portfolio Value ($)")
        ax1.set_title(f"{self.strategy_name} - Equity Curve")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Drawdown
        ax2 = axes[1]
        rolling_max = self.equity_curve.expanding().max()
        drawdown = (self.equity_curve - rolling_max) / rolling_max * 100
        drawdown.plot(ax=ax2, color="red", linewidth=1)
        ax2.fill_between(drawdown.index, drawdown.values, 0, alpha=0.3, color="red")
        ax2.set_ylabel("Drawdown (%)")
        ax2.set_xlabel("Date")
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig


class BacktestEngine:
    """
    Event-driven backtesting engine.

    Processes historical data bar-by-bar, executing strategy signals.
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission: float = 0.0,
        slippage: float = 0.001,
    ):
        """
        Initialize backtest engine.

        Args:
            initial_capital: Starting capital
            commission: Commission per trade
            slippage: Slippage rate (as decimal)
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

    def run(
        self,
        strategy: Strategy,
        data: pd.DataFrame,
        symbol: str = None,
    ) -> BacktestResult:
        """
        Run backtest.

        Args:
            strategy: Strategy instance to backtest
            data: DataFrame with OHLCV data (DatetimeIndex)
            symbol: Symbol being traded (defaults to 'ASSET')

        Returns:
            BacktestResult with performance data
        """
        if len(data) == 0:
            raise ValueError("Empty data provided")

        symbol = symbol or "ASSET"

        # Initialize portfolio
        portfolio = Portfolio(initial_cash=self.initial_capital, commission=self.commission)

        # Set strategy context
        strategy.set_context(portfolio, None, data.iloc[:0])  # Empty history initially
        strategy.on_start()

        all_signals = []

        # Process each bar
        for i, (timestamp, bar) in enumerate(data.iterrows()):
            # Update strategy's view of history
            history = data.iloc[: i + 1]
            strategy._history = history

            # Update portfolio prices
            current_price = bar["Close"]
            portfolio.update_prices({symbol: current_price})

            # Get signals from strategy
            signals = strategy.on_bar(bar)

            # Process signals
            for signal in signals:
                if signal.action == "hold":
                    continue

                sig_symbol = signal.symbol or symbol
                price = signal.price or current_price

                # Apply slippage
                if signal.action == "buy":
                    exec_price = price * (1 + self.slippage)
                else:
                    exec_price = price * (1 - self.slippage)

                # Determine quantity
                if signal.quantity is None:
                    # Default position sizing: 10% of equity per trade
                    position_value = portfolio.total_equity * 0.1
                    quantity = position_value // exec_price
                else:
                    quantity = signal.quantity

                if quantity <= 0:
                    continue

                # Execute trade
                if signal.action == "buy":
                    success = portfolio.buy(sig_symbol, quantity, exec_price, timestamp)
                elif signal.action == "sell":
                    success = portfolio.sell(sig_symbol, quantity, exec_price, timestamp)
                else:
                    success = False

                # Record signal
                all_signals.append({
                    "timestamp": timestamp,
                    "symbol": sig_symbol,
                    "action": signal.action,
                    "quantity": quantity,
                    "price": exec_price,
                    "reason": signal.reason,
                    "executed": success,
                })

            # Record portfolio state
            portfolio.record_state(timestamp)

        strategy.on_end()

        # Calculate metrics
        equity_curve = portfolio.equity_curve()
        trades_df = portfolio.trades_df()

        metrics = PerformanceMetrics.from_equity_curve(
            equity_curve,
            trades_df if len(trades_df) > 0 else None,
        )

        return BacktestResult(
            strategy_name=strategy.name,
            start_date=data.index[0].to_pydatetime() if hasattr(data.index[0], 'to_pydatetime') else data.index[0],
            end_date=data.index[-1].to_pydatetime() if hasattr(data.index[-1], 'to_pydatetime') else data.index[-1],
            initial_capital=self.initial_capital,
            final_equity=portfolio.total_equity,
            total_return=portfolio.total_return,
            metrics=metrics,
            equity_curve=equity_curve,
            trades=trades_df,
            signals=all_signals,
        )

    def run_multiple(
        self,
        strategies: list[Strategy],
        data: pd.DataFrame,
        symbol: str = None,
    ) -> dict[str, BacktestResult]:
        """
        Run multiple strategies on the same data.

        Args:
            strategies: List of strategy instances
            data: DataFrame with OHLCV data
            symbol: Symbol being traded

        Returns:
            Dictionary mapping strategy names to results
        """
        results = {}
        for strategy in strategies:
            results[strategy.name] = self.run(strategy, data, symbol)
        return results

    def compare(
        self,
        results: dict[str, BacktestResult],
        benchmark: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        """
        Compare multiple backtest results.

        Args:
            results: Dictionary of backtest results
            benchmark: Optional benchmark returns

        Returns:
            DataFrame comparing strategies
        """
        comparison_data = []

        for name, result in results.items():
            comparison_data.append({
                "Strategy": name,
                "Total Return": result.total_return,
                "Annualized Return": result.metrics.annualized_return,
                "Volatility": result.metrics.volatility,
                "Sharpe": result.metrics.sharpe_ratio,
                "Sortino": result.metrics.sortino_ratio,
                "Max Drawdown": result.metrics.max_drawdown,
                "Win Rate": result.metrics.win_rate,
                "Num Trades": result.metrics.num_trades,
            })

        df = pd.DataFrame(comparison_data)
        df.set_index("Strategy", inplace=True)
        return df
