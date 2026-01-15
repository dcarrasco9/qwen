"""
Options-based trading strategies.

These strategies simulate options positions using the pricing models,
tracking P&L as if holding actual options contracts.
"""

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np

from qwen.backtest import Strategy, Signal
from qwen.pricing import BlackScholes


@dataclass
class OptionPosition:
    """Tracks a simulated option position."""
    option_type: str  # 'call' or 'put'
    strike: float
    expiry_date: datetime
    premium: float  # Premium paid/received per share
    quantity: int  # Positive = long, negative = short
    entry_date: datetime

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    def value(self, spot: float, current_date: datetime, vol: float = 0.25, rate: float = 0.05) -> float:
        """Calculate current option value."""
        days_to_expiry = (self.expiry_date - current_date).days
        if days_to_expiry <= 0:
            # At expiration - intrinsic value only
            if self.option_type == 'call':
                intrinsic = max(0, spot - self.strike)
            else:
                intrinsic = max(0, self.strike - spot)
            return intrinsic * abs(self.quantity) * 100

        time_to_expiry = days_to_expiry / 365
        bs = BlackScholes(spot, self.strike, rate, vol, time_to_expiry)
        price = bs.call_price() if self.option_type == 'call' else bs.put_price()
        return price * abs(self.quantity) * 100

    def pnl(self, spot: float, current_date: datetime, vol: float = 0.25) -> float:
        """Calculate P&L of the position."""
        current_value = self.value(spot, current_date, vol)
        cost = self.premium * abs(self.quantity) * 100

        if self.is_long:
            return current_value - cost
        else:
            return cost - current_value


class CoveredCallStrategy(Strategy):
    """
    Covered Call: Long stock + Short OTM call.

    - Generates income from premium in flat/down markets
    - Caps upside if stock rallies past strike
    - Best for: Neutral to slightly bullish outlook
    """

    def __init__(self, symbol: str, delta_target: float = 0.30, days_to_expiry: int = 30):
        super().__init__(f"CoveredCall_{symbol}")
        self.symbol = symbol
        self.delta_target = delta_target
        self.dte = days_to_expiry
        self.shares = 0
        self.call_position: Optional[OptionPosition] = None
        self.total_premium_collected = 0
        self.vol = 0.25

    def on_start(self):
        self.shares = 0
        self.call_position = None
        self.total_premium_collected = 0

    def _find_strike_for_delta(self, spot: float, target_delta: float, dte: int) -> tuple[float, float]:
        """Find strike price that gives target delta, return (strike, premium)."""
        time_to_expiry = dte / 365

        # Binary search for strike
        low, high = spot * 0.9, spot * 1.3
        for _ in range(20):
            mid = (low + high) / 2
            bs = BlackScholes(spot, mid, 0.05, self.vol, time_to_expiry)
            delta = bs.delta('call')

            if delta > target_delta:
                low = mid
            else:
                high = mid

        strike = round(mid, 0)
        bs = BlackScholes(spot, strike, 0.05, self.vol, time_to_expiry)
        premium = bs.call_price()
        return strike, premium

    def on_bar(self, bar) -> list:
        signals = []
        price = bar['Close']
        current_date = bar.name.to_pydatetime() if hasattr(bar.name, 'to_pydatetime') else datetime.now()

        # Buy shares if we don't have them
        if self.shares == 0:
            signals.append(Signal(symbol=self.symbol, action='buy', quantity=100, reason='Initial stock purchase'))
            self.shares = 100

            # Sell initial call
            strike, premium = self._find_strike_for_delta(price, self.delta_target, self.dte)
            self.call_position = OptionPosition(
                option_type='call',
                strike=strike,
                expiry_date=current_date + timedelta(days=self.dte),
                premium=premium,
                quantity=-1,  # Short
                entry_date=current_date
            )
            self.total_premium_collected += premium * 100
            return signals

        # Check if call expired or needs rolling
        if self.call_position:
            days_left = (self.call_position.expiry_date - current_date).days

            if days_left <= 1:
                # Roll the call
                # Close old position (buy back)
                old_value = self.call_position.value(price, current_date, self.vol)

                # Open new position
                strike, premium = self._find_strike_for_delta(price, self.delta_target, self.dte)
                self.call_position = OptionPosition(
                    option_type='call',
                    strike=strike,
                    expiry_date=current_date + timedelta(days=self.dte),
                    premium=premium,
                    quantity=-1,
                    entry_date=current_date
                )
                self.total_premium_collected += premium * 100

        return signals

    def on_end(self):
        pass  # Summary printed by caller


class CashSecuredPutStrategy(Strategy):
    """
    Cash-Secured Put: Sell OTM puts, collect premium.

    - Collect premium if stock stays above strike
    - Get assigned shares at discount if stock drops
    - Best for: Bullish outlook, wanting to buy at lower price
    """

    def __init__(self, symbol: str, delta_target: float = -0.25, days_to_expiry: int = 30):
        super().__init__(f"CashSecuredPut_{symbol}")
        self.symbol = symbol
        self.delta_target = delta_target
        self.dte = days_to_expiry
        self.put_position: Optional[OptionPosition] = None
        self.assigned_shares = 0
        self.total_premium = 0
        self.vol = 0.25
        self.cash_reserved = 0

    def _find_put_strike(self, spot: float, target_delta: float, dte: int) -> tuple[float, float]:
        """Find put strike for target delta."""
        time_to_expiry = dte / 365

        # Put delta is negative, so -0.25 delta means ~25% ITM probability
        # Search from slightly OTM to ATM
        low, high = spot * 0.85, spot * 1.05
        for _ in range(25):
            mid = (low + high) / 2
            bs = BlackScholes(spot, mid, 0.05, self.vol, time_to_expiry)
            delta = bs.delta('put')

            # Put delta is negative: more negative = more ITM
            if delta < target_delta:  # e.g., -0.30 < -0.25
                high = mid  # Strike too high, go lower
            else:
                low = mid

        strike = round(mid, 0)
        bs = BlackScholes(spot, strike, 0.05, self.vol, time_to_expiry)
        premium = bs.put_price()
        return strike, premium

    def on_bar(self, bar) -> list:
        signals = []
        price = bar['Close']
        current_date = bar.name.to_pydatetime() if hasattr(bar.name, 'to_pydatetime') else datetime.now()

        # If we got assigned shares, hold them
        if self.assigned_shares > 0:
            return signals

        # Sell put if we don't have one
        if self.put_position is None:
            strike, premium = self._find_put_strike(price, self.delta_target, self.dte)
            self.put_position = OptionPosition(
                option_type='put',
                strike=strike,
                expiry_date=current_date + timedelta(days=self.dte),
                premium=premium,
                quantity=-1,
                entry_date=current_date
            )
            self.total_premium += premium * 100
            self.cash_reserved = strike * 100  # Reserve cash for potential assignment
            return signals

        # Check expiration
        days_left = (self.put_position.expiry_date - current_date).days

        if days_left <= 1:
            # Check if ITM (assigned)
            if price < self.put_position.strike:
                # Assigned - buy shares at strike
                signals.append(Signal(
                    symbol=self.symbol,
                    action='buy',
                    quantity=100,
                    price=self.put_position.strike,
                    reason=f'Put assignment at ${self.put_position.strike}'
                ))
                self.assigned_shares = 100
                self.put_position = None
            else:
                # Expired worthless - sell new put
                strike, premium = self._find_put_strike(price, self.delta_target, self.dte)
                self.put_position = OptionPosition(
                    option_type='put',
                    strike=strike,
                    expiry_date=current_date + timedelta(days=self.dte),
                    premium=premium,
                    quantity=-1,
                    entry_date=current_date
                )
                self.total_premium += premium * 100

        return signals

    def on_end(self):
        pass


class IronCondorStrategy(Strategy):
    """
    Iron Condor: Sell OTM put spread + Sell OTM call spread.

    - Profit if stock stays within range
    - Limited risk, limited reward
    - Best for: Low volatility, range-bound markets
    """

    def __init__(self, symbol: str, put_delta: float = -0.15, call_delta: float = 0.15,
                 wing_width: float = 5, days_to_expiry: int = 30):
        super().__init__(f"IronCondor_{symbol}")
        self.symbol = symbol
        self.put_delta = put_delta
        self.call_delta = call_delta
        self.wing_width = wing_width
        self.dte = days_to_expiry
        self.position_open = False
        self.total_premium = 0
        self.total_pnl = 0
        self.trades_count = 0
        self.vol = 0.25

    def _find_strikes(self, spot: float, dte: int) -> dict:
        """Find all four strikes for iron condor."""
        time_to_expiry = dte / 365

        # Find short put strike (sell)
        low, high = spot * 0.7, spot * 0.95
        for _ in range(20):
            mid = (low + high) / 2
            bs = BlackScholes(spot, mid, 0.05, self.vol, time_to_expiry)
            if bs.delta('put') < self.put_delta:
                low = mid
            else:
                high = mid
        short_put = round(mid, 0)

        # Find short call strike (sell)
        low, high = spot * 1.05, spot * 1.3
        for _ in range(20):
            mid = (low + high) / 2
            bs = BlackScholes(spot, mid, 0.05, self.vol, time_to_expiry)
            if bs.delta('call') > self.call_delta:
                low = mid
            else:
                high = mid
        short_call = round(mid, 0)

        # Long strikes (wings)
        long_put = short_put - self.wing_width
        long_call = short_call + self.wing_width

        # Calculate net credit
        bs_sp = BlackScholes(spot, short_put, 0.05, self.vol, time_to_expiry)
        bs_lp = BlackScholes(spot, long_put, 0.05, self.vol, time_to_expiry)
        bs_sc = BlackScholes(spot, short_call, 0.05, self.vol, time_to_expiry)
        bs_lc = BlackScholes(spot, long_call, 0.05, self.vol, time_to_expiry)

        credit = (bs_sp.put_price() - bs_lp.put_price() +
                  bs_sc.call_price() - bs_lc.call_price())

        return {
            'short_put': short_put,
            'long_put': long_put,
            'short_call': short_call,
            'long_call': long_call,
            'credit': credit
        }

    def _calc_pnl_at_expiry(self, spot: float, strikes: dict) -> float:
        """Calculate P&L at expiration."""
        credit = strikes['credit'] * 100

        # Calculate intrinsic values
        sp, lp = strikes['short_put'], strikes['long_put']
        sc, lc = strikes['short_call'], strikes['long_call']

        # Put spread P&L
        if spot <= lp:
            put_pnl = -(sp - lp) * 100  # Max loss on put side
        elif spot <= sp:
            put_pnl = -(sp - spot) * 100
        else:
            put_pnl = 0

        # Call spread P&L
        if spot >= lc:
            call_pnl = -(lc - sc) * 100  # Max loss on call side
        elif spot >= sc:
            call_pnl = -(spot - sc) * 100
        else:
            call_pnl = 0

        return credit + put_pnl + call_pnl

    def on_bar(self, bar) -> list:
        price = bar['Close']
        current_date = bar.name.to_pydatetime() if hasattr(bar.name, 'to_pydatetime') else datetime.now()

        if not self.position_open:
            # Open new iron condor
            self.strikes = self._find_strikes(price, self.dte)
            self.expiry_date = current_date + timedelta(days=self.dte)
            self.total_premium += self.strikes['credit'] * 100
            self.position_open = True
            self.trades_count += 1
            return []

        # Check expiration
        days_left = (self.expiry_date - current_date).days
        if days_left <= 1:
            # Calculate P&L at expiry
            pnl = self._calc_pnl_at_expiry(price, self.strikes)
            self.total_pnl += pnl
            self.position_open = False

        return []

    def on_end(self):
        pass


class StraddleStrategy(Strategy):
    """
    Long Straddle: Buy ATM call + ATM put.

    - Profit from large moves in either direction
    - Lose if stock stays flat (theta decay)
    - Best for: High volatility expected, direction uncertain
    """

    def __init__(self, symbol: str, days_to_expiry: int = 30,
                 profit_target: float = 0.5, stop_loss: float = -0.3):
        super().__init__(f"Straddle_{symbol}")
        self.symbol = symbol
        self.dte = days_to_expiry
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        self.position: Optional[dict] = None
        self.total_pnl = 0
        self.trades = 0
        self.wins = 0
        self.vol = 0.30

    def on_bar(self, bar) -> list:
        price = bar['Close']
        current_date = bar.name.to_pydatetime() if hasattr(bar.name, 'to_pydatetime') else datetime.now()

        if self.position is None:
            # Open straddle
            strike = round(price, 0)
            time_to_expiry = self.dte / 365
            bs = BlackScholes(price, strike, 0.05, self.vol, time_to_expiry)

            call_premium = bs.call_price()
            put_premium = bs.put_price()
            total_cost = (call_premium + put_premium) * 100

            self.position = {
                'strike': strike,
                'expiry': current_date + timedelta(days=self.dte),
                'cost': total_cost,
                'entry_price': price
            }
            self.trades += 1
            return []

        # Check current P&L
        days_left = (self.position['expiry'] - current_date).days
        time_to_expiry = max(days_left / 365, 0.001)

        bs = BlackScholes(price, self.position['strike'], 0.05, self.vol, time_to_expiry)
        current_value = (bs.call_price() + bs.put_price()) * 100
        pnl_pct = (current_value - self.position['cost']) / self.position['cost']

        # Check exit conditions
        close_position = False

        if pnl_pct >= self.profit_target:
            close_position = True
            self.wins += 1
        elif pnl_pct <= self.stop_loss:
            close_position = True
        elif days_left <= 1:
            close_position = True
            if pnl_pct > 0:
                self.wins += 1

        if close_position:
            self.total_pnl += current_value - self.position['cost']
            self.position = None

        return []

    def on_end(self):
        pass


def run_options_backtest():
    """Run backtests on all options strategies."""
    from qwen.data import YahooDataProvider
    from qwen.backtest import BacktestEngine

    provider = YahooDataProvider()
    engine = BacktestEngine(initial_capital=100_000, commission=1.0, slippage=0.001)

    print("OPTIONS STRATEGIES BACKTEST")
    print("="*70)

    for symbol in ['TSLA', 'NVDA', 'AMD']:
        data = provider.get_historical(symbol)
        buyhold = (data["Close"].iloc[-1] / data["Close"].iloc[0] - 1)

        print(f"\n{symbol} (Buy&Hold: {buyhold:+.1%})")
        print("-"*70)

        strategies = [
            CoveredCallStrategy(symbol, delta_target=0.30, days_to_expiry=30),
            CashSecuredPutStrategy(symbol, delta_target=-0.25, days_to_expiry=30),
            IronCondorStrategy(symbol, days_to_expiry=30),
            StraddleStrategy(symbol, days_to_expiry=21),
        ]

        for strat in strategies:
            result = engine.run(strat, data, symbol=symbol)
            print(f"\n{strat.name}:")
            print(f"  Return: {result.total_return:+.2%}")
            print(f"  Max Drawdown: {result.metrics.max_drawdown:.2%}")


if __name__ == "__main__":
    run_options_backtest()
