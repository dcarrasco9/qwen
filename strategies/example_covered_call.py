"""
Example: Covered Call Strategy

A covered call strategy involves:
1. Holding shares of the underlying stock (long position)
2. Selling call options against those shares to collect premium

This generates income in flat/sideways markets but caps upside potential.
"""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from qwen.backtest.strategy import Strategy, Signal
from qwen.pricing import BlackScholes
from qwen.data import YahooDataProvider


class CoveredCallStrategy(Strategy):
    """
    Covered call options strategy.

    - Buys 100 shares of underlying
    - Sells 1 call option (covering the 100 shares)
    - Rolls the call at expiration or when profitable
    """

    def __init__(
        self,
        symbol: str,
        days_to_expiry: int = 30,
        delta_target: float = 0.30,
        roll_profit_threshold: float = 0.50,
    ):
        """
        Initialize covered call strategy.

        Args:
            symbol: Underlying symbol
            days_to_expiry: Target days to expiration for calls
            delta_target: Target delta for short call (0.30 = ~30% ITM probability)
            roll_profit_threshold: Roll when option at this % of original premium
        """
        super().__init__(f"CoveredCall_{symbol}")
        self.symbol = symbol
        self.days_to_expiry = days_to_expiry
        self.delta_target = delta_target
        self.roll_profit_threshold = roll_profit_threshold

        # Track our option position
        self.call_strike: Optional[float] = None
        self.call_expiry: Optional[datetime] = None
        self.call_premium: float = 0
        self.shares_held: int = 0

    def on_start(self):
        """Initialize strategy state."""
        self.call_strike = None
        self.call_expiry = None
        self.call_premium = 0
        self.shares_held = 0

    def on_bar(self, bar: pd.Series) -> list[Signal]:
        """
        Process each bar.

        Logic:
        1. If no shares, buy 100 shares
        2. If shares but no call, sell a call
        3. If call is near expiry or profitable, roll it
        """
        signals = []
        current_price = bar["Close"]
        current_date = bar.name if hasattr(bar, "name") else datetime.now()

        # Ensure we have shares
        if self.shares_held == 0:
            signals.append(Signal(
                symbol=self.symbol,
                action="buy",
                quantity=100,
                reason="Initiate covered call position",
            ))
            self.shares_held = 100

            # Also sell a call
            self._sell_call(current_price, current_date)
            return signals

        # Check if we need to roll the call
        if self.call_strike is not None and self.call_expiry is not None:
            days_remaining = (self.call_expiry - current_date).days if isinstance(current_date, datetime) else 0

            # Roll conditions:
            # 1. Near expiration (< 5 days)
            # 2. Option is cheap enough to buy back profitably
            should_roll = False

            if days_remaining <= 5:
                should_roll = True
                reason = f"Rolling - {days_remaining} days to expiry"

            # Check current option value
            if not should_roll:
                time_to_expiry = max(days_remaining / 365, 0.001)
                bs = BlackScholes(
                    spot=current_price,
                    strike=self.call_strike,
                    rate=0.05,
                    volatility=0.25,  # Assumed vol
                    time_to_expiry=time_to_expiry,
                )
                current_call_value = bs.call_price()

                if current_call_value <= self.call_premium * self.roll_profit_threshold:
                    should_roll = True
                    reason = f"Rolling - option at {current_call_value/self.call_premium:.0%} of premium"

            if should_roll:
                # Buy back old call (simulated) and sell new one
                self._sell_call(current_price, current_date)

        return signals

    def _sell_call(self, current_price: float, current_date):
        """
        Find and sell a call option targeting our delta.

        This is a simplified simulation - in reality you'd query the options chain.
        """
        # Target expiration
        if isinstance(current_date, datetime):
            self.call_expiry = current_date + timedelta(days=self.days_to_expiry)
        else:
            self.call_expiry = datetime.now() + timedelta(days=self.days_to_expiry)

        # Find strike for target delta using Black-Scholes
        # Delta ≈ N(d1), so we iterate to find the right strike
        time_to_expiry = self.days_to_expiry / 365
        volatility = 0.25  # Assumed IV

        # Binary search for strike that gives target delta
        low_strike = current_price * 0.9
        high_strike = current_price * 1.3

        for _ in range(20):
            mid_strike = (low_strike + high_strike) / 2
            bs = BlackScholes(
                spot=current_price,
                strike=mid_strike,
                rate=0.05,
                volatility=volatility,
                time_to_expiry=time_to_expiry,
            )
            delta = bs.delta("call")

            if delta > self.delta_target:
                low_strike = mid_strike
            else:
                high_strike = mid_strike

            if abs(delta - self.delta_target) < 0.01:
                break

        self.call_strike = round(mid_strike, 0)  # Round to nearest dollar

        # Calculate premium received
        bs = BlackScholes(
            spot=current_price,
            strike=self.call_strike,
            rate=0.05,
            volatility=volatility,
            time_to_expiry=time_to_expiry,
        )
        self.call_premium = bs.call_price() * 100  # Per contract (100 shares)

    def on_end(self):
        """Strategy cleanup."""
        print(f"\n{self.name} Summary:")
        print(f"  Final call strike: ${self.call_strike}")
        print(f"  Shares held: {self.shares_held}")


def run_example():
    """Run a simple covered call backtest."""
    from qwen.data import YahooDataProvider
    from qwen.backtest import BacktestEngine

    # Get historical data
    provider = YahooDataProvider()
    data = provider.get_historical("AAPL", interval="1d")

    # Create strategy
    strategy = CoveredCallStrategy("AAPL", days_to_expiry=30, delta_target=0.30)

    # Run backtest
    engine = BacktestEngine(initial_capital=50_000, commission=1.0)
    result = engine.run(strategy, data, symbol="AAPL")

    # Print results
    print("\nBacktest Results:")
    for key, value in result.summary().items():
        print(f"  {key}: {value}")

    return result


if __name__ == "__main__":
    run_example()
