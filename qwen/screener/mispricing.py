"""
Options Mispricing Detection

Identifies potential arbitrage and value opportunities in options markets:
1. Put-Call Parity Violations (using EXECUTABLE prices, not mid)
2. Implied vs Realized Volatility Discrepancies
3. Skew Anomalies
4. Term Structure Opportunities

IMPORTANT: This scanner uses executable prices (bid for sells, ask for buys)
to filter out false positives caused by wide bid-ask spreads.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal, Optional

import numpy as np
import pandas as pd

from qwen.data.base import DataProvider, OptionContract
from qwen.pricing import BlackScholes

logger = logging.getLogger(__name__)


@dataclass
class MispricingOpportunity:
    """Represents a detected mispricing opportunity."""

    symbol: str
    opportunity_type: str  # 'put_call_parity', 'iv_discount', 'skew_anomaly', etc.
    description: str
    theoretical_value: float
    market_value: float
    edge: float  # Theoretical - Market (positive = underpriced)
    edge_pct: float
    confidence: float  # 0-1 confidence score
    suggested_trade: str
    risk_reward: float
    timestamp: datetime = None

    # New fields for realistic execution analysis
    executable_edge: float = 0.0  # Edge after accounting for bid-ask spread
    executable_edge_pct: float = 0.0
    bid_ask_spread_pct: float = 0.0  # Spread as % of mid price
    volume: int = 0
    open_interest: int = 0
    liquidity_score: float = 0.0  # 0-1 score combining volume, OI, spread

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    @property
    def is_actionable(self) -> bool:
        """
        Check if opportunity meets minimum thresholds.

        Now requires EXECUTABLE edge to be positive, not just theoretical edge.
        """
        return (
            self.executable_edge_pct > 2.0  # Must have >2% edge after spreads
            and self.confidence > 0.5
            and self.liquidity_score > 0.3  # Must be reasonably liquid
            and self.bid_ask_spread_pct < 20  # Spread must be <20% of mid
        )


def calculate_liquidity_score(
    volume: int,
    open_interest: int,
    bid_ask_spread_pct: float,
    min_volume: int = 100,
    min_oi: int = 500,
) -> float:
    """
    Calculate a liquidity score from 0-1.

    Factors:
    - Volume relative to minimum (higher = better)
    - Open interest relative to minimum (higher = better)
    - Bid-ask spread (lower = better)
    """
    # Volume score (0-1)
    vol_score = min(1.0, volume / (min_volume * 10))

    # OI score (0-1)
    oi_score = min(1.0, open_interest / (min_oi * 10))

    # Spread score (0-1, lower spread = higher score)
    # 0% spread = 1.0, 50%+ spread = 0.0
    spread_score = max(0.0, 1.0 - bid_ask_spread_pct / 50)

    # Weighted average
    return 0.3 * vol_score + 0.3 * oi_score + 0.4 * spread_score


def get_bid_ask_spread_pct(opt: OptionContract) -> float:
    """Calculate bid-ask spread as percentage of mid price."""
    if not opt.bid or not opt.ask or opt.ask <= 0:
        return 100.0  # No valid quotes = 100% spread (unusable)

    mid = (opt.bid + opt.ask) / 2
    if mid <= 0:
        return 100.0

    spread = opt.ask - opt.bid
    return (spread / mid) * 100


class MispricingScanner:
    """
    Scans options chains for mispricing opportunities.

    IMPORTANT: Uses EXECUTABLE prices (bid for sells, ask for buys) to avoid
    false positives from wide bid-ask spreads.

    Looks for:
    - Put-call parity violations (risk-free arbitrage)
    - IV significantly below realized volatility (cheap options)
    - IV significantly above realized volatility (expensive options)
    - Skew anomalies (unusual strike pricing)
    - Calendar spread opportunities (term structure)
    """

    def __init__(
        self,
        data_provider: DataProvider,
        risk_free_rate: float = 0.05,
        min_edge_pct: float = 5.0,
        min_volume: int = 100,
        min_open_interest: int = 100,
        max_spread_pct: float = 25.0,
        use_executable_prices: bool = True,
    ):
        """
        Initialize scanner.

        Args:
            data_provider: Data provider for quotes and chains
            risk_free_rate: Risk-free rate for calculations
            min_edge_pct: Minimum theoretical edge percentage to consider
            min_volume: Minimum option volume to consider
            min_open_interest: Minimum open interest to consider
            max_spread_pct: Maximum bid-ask spread as % of mid to consider
            use_executable_prices: If True, use bid/ask for edge calculation.
                                   If False, use mid prices (legacy behavior).
        """
        self.provider = data_provider
        self.rate = risk_free_rate
        self.min_edge_pct = min_edge_pct
        self.min_volume = min_volume
        self.min_open_interest = min_open_interest
        self.max_spread_pct = max_spread_pct
        self.use_executable_prices = use_executable_prices

    def _get_executable_price(self, opt: OptionContract, action: str) -> Optional[float]:
        """
        Get the executable price for an option.

        Args:
            opt: The option contract
            action: 'buy' or 'sell'

        Returns:
            The executable price (ask for buys, bid for sells)
        """
        if action == 'buy':
            # You pay the ask to buy
            return opt.ask if opt.ask and opt.ask > 0 else None
        else:
            # You receive the bid to sell
            return opt.bid if opt.bid and opt.bid > 0 else None

    def _passes_liquidity_filter(self, opt: OptionContract) -> bool:
        """Check if option passes minimum liquidity requirements."""
        if opt.volume < self.min_volume:
            return False
        if opt.open_interest < self.min_open_interest:
            return False

        spread_pct = get_bid_ask_spread_pct(opt)
        if spread_pct > self.max_spread_pct:
            return False

        return True

    def scan_symbol(self, symbol: str) -> list[MispricingOpportunity]:
        """
        Scan a single symbol for mispricing opportunities.

        Args:
            symbol: Stock symbol to scan

        Returns:
            List of detected opportunities
        """
        opportunities = []

        try:
            # Get current price and historical data
            end = datetime.now()
            start = end - timedelta(days=60)
            history = self.provider.get_historical(symbol, start, end)

            if history.empty:
                return opportunities

            spot = history['Close'].iloc[-1]

            # Calculate realized volatility (20-day)
            returns = history['Close'].pct_change().dropna()
            realized_vol = returns.tail(20).std() * np.sqrt(252)

            # Get options chain
            chain = self.provider.get_options_chain(symbol)
            if not chain:
                return opportunities

            # Group by expiration
            by_expiry = {}
            for opt in chain:
                exp_key = opt.expiration.strftime('%Y-%m-%d')
                if exp_key not in by_expiry:
                    by_expiry[exp_key] = []
                by_expiry[exp_key].append(opt)

            # Scan each expiration
            for expiry, options in by_expiry.items():
                exp_date = datetime.strptime(expiry, '%Y-%m-%d')
                days_to_exp = (exp_date - datetime.now()).days

                if days_to_exp <= 0:
                    continue

                time_to_exp = days_to_exp / 365

                # 1. Check put-call parity
                parity_opps = self._check_put_call_parity(
                    symbol, spot, options, time_to_exp, expiry
                )
                opportunities.extend(parity_opps)

                # 2. Check IV vs realized vol
                vol_opps = self._check_iv_vs_realized(
                    symbol, spot, options, realized_vol, time_to_exp, expiry
                )
                opportunities.extend(vol_opps)

                # 3. Check skew anomalies
                skew_opps = self._check_skew_anomalies(
                    symbol, spot, options, time_to_exp, expiry
                )
                opportunities.extend(skew_opps)

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")

        return opportunities

    def _check_put_call_parity(
        self,
        symbol: str,
        spot: float,
        options: list[OptionContract],
        time_to_exp: float,
        expiry: str,
    ) -> list[MispricingOpportunity]:
        """
        Check for put-call parity violations using EXECUTABLE prices.

        Put-Call Parity: C - P = S - K*e^(-rT)

        For a Conversion (sell call, buy put, buy stock):
          - Sell call at BID
          - Buy put at ASK
          - Buy stock at current price

        For a Reversal (sell put, buy call, short stock):
          - Sell put at BID
          - Buy call at ASK
          - Short stock at current price

        The executable edge must be positive for a real arbitrage.
        """
        opportunities = []

        # Group by strike
        calls = {o.strike: o for o in options if o.option_type == 'call'}
        puts = {o.strike: o for o in options if o.option_type == 'put'}

        for strike in set(calls.keys()) & set(puts.keys()):
            call = calls[strike]
            put = puts[strike]

            # Calculate spread percentages
            call_spread_pct = get_bid_ask_spread_pct(call)
            put_spread_pct = get_bid_ask_spread_pct(put)
            avg_spread_pct = (call_spread_pct + put_spread_pct) / 2

            # Skip if spreads are too wide
            if call_spread_pct > self.max_spread_pct or put_spread_pct > self.max_spread_pct:
                continue

            # Skip low volume/OI
            if call.volume < self.min_volume or put.volume < self.min_volume:
                continue
            if call.open_interest < self.min_open_interest or put.open_interest < self.min_open_interest:
                continue

            # Get prices
            call_bid = call.bid if call.bid else 0
            call_ask = call.ask if call.ask else 0
            put_bid = put.bid if put.bid else 0
            put_ask = put.ask if put.ask else 0

            call_mid = (call_bid + call_ask) / 2 if call_bid and call_ask else call.last
            put_mid = (put_bid + put_ask) / 2 if put_bid and put_ask else put.last

            if not call_mid or not put_mid:
                continue

            # Theoretical relationship
            pv_strike = strike * np.exp(-self.rate * time_to_exp)
            theoretical_diff = spot - pv_strike  # C - P should equal this

            # Calculate violation using MID prices (theoretical)
            actual_diff_mid = call_mid - put_mid
            violation_mid = actual_diff_mid - theoretical_diff

            # Calculate violation using EXECUTABLE prices
            # Conversion: sell call (get bid), buy put (pay ask)
            conversion_diff = call_bid - put_ask
            conversion_violation = conversion_diff - theoretical_diff

            # Reversal: sell put (get bid), buy call (pay ask)
            reversal_diff = call_ask - put_bid
            reversal_violation = reversal_diff - theoretical_diff

            # Determine if there's a real arbitrage
            has_conversion_arb = conversion_violation > 0.05  # $0.05 min after spreads
            has_reversal_arb = reversal_violation < -0.05

            # Skip if no executable arbitrage
            if not has_conversion_arb and not has_reversal_arb:
                continue

            # Calculate liquidity score
            combined_volume = call.volume + put.volume
            combined_oi = call.open_interest + put.open_interest
            liquidity = calculate_liquidity_score(
                combined_volume, combined_oi, avg_spread_pct,
                self.min_volume * 2, self.min_open_interest * 2
            )

            if has_conversion_arb:
                # Call overpriced relative to put - do conversion
                executable_edge = conversion_violation
                edge_pct_mid = (violation_mid / call_mid) * 100 if call_mid else 0
                executable_edge_pct = (executable_edge / call_mid) * 100 if call_mid else 0
                trade = f"CONVERSION: Sell {symbol} ${strike}C @${call_bid:.2f}, Buy ${strike}P @${put_ask:.2f}, Buy Stock"

                opportunities.append(MispricingOpportunity(
                    symbol=symbol,
                    opportunity_type="put_call_parity",
                    description=f"Put-call parity: Conversion at ${strike} ({expiry})",
                    theoretical_value=theoretical_diff,
                    market_value=actual_diff_mid,
                    edge=violation_mid,
                    edge_pct=edge_pct_mid,
                    confidence=0.9 if executable_edge > 0.10 else 0.7,
                    suggested_trade=trade,
                    risk_reward=10.0 if executable_edge > 0 else 0.0,
                    executable_edge=executable_edge,
                    executable_edge_pct=executable_edge_pct,
                    bid_ask_spread_pct=avg_spread_pct,
                    volume=combined_volume,
                    open_interest=combined_oi,
                    liquidity_score=liquidity,
                ))

            if has_reversal_arb:
                # Put overpriced relative to call - do reversal
                executable_edge = -reversal_violation
                edge_pct_mid = (violation_mid / put_mid) * 100 if put_mid else 0
                executable_edge_pct = (executable_edge / put_mid) * 100 if put_mid else 0
                trade = f"REVERSAL: Sell {symbol} ${strike}P @${put_bid:.2f}, Buy ${strike}C @${call_ask:.2f}, Short Stock"

                opportunities.append(MispricingOpportunity(
                    symbol=symbol,
                    opportunity_type="put_call_parity",
                    description=f"Put-call parity: Reversal at ${strike} ({expiry})",
                    theoretical_value=theoretical_diff,
                    market_value=actual_diff_mid,
                    edge=violation_mid,
                    edge_pct=edge_pct_mid,
                    confidence=0.9 if executable_edge > 0.10 else 0.7,
                    suggested_trade=trade,
                    risk_reward=10.0 if executable_edge > 0 else 0.0,
                    executable_edge=executable_edge,
                    executable_edge_pct=executable_edge_pct,
                    bid_ask_spread_pct=avg_spread_pct,
                    volume=combined_volume,
                    open_interest=combined_oi,
                    liquidity_score=liquidity,
                ))

        return opportunities

    def _check_iv_vs_realized(
        self,
        symbol: str,
        spot: float,
        options: list[OptionContract],
        realized_vol: float,
        time_to_exp: float,
        expiry: str,
    ) -> list[MispricingOpportunity]:
        """
        Check for IV significantly different from realized volatility.

        - IV << Realized: Options are cheap (buy at ASK)
        - IV >> Realized: Options are expensive (sell at BID)

        Accounts for bid-ask spread in determining executable edge.
        """
        opportunities = []

        for opt in options:
            # Liquidity filters
            if not self._passes_liquidity_filter(opt):
                continue

            iv = opt.implied_volatility
            if not iv or iv <= 0:
                continue

            # Calculate IV premium/discount vs realized
            iv_ratio = iv / realized_vol if realized_vol > 0 else 1

            # Get prices
            mid = (opt.bid + opt.ask) / 2 if opt.bid and opt.ask else opt.last
            if not mid or mid <= 0:
                continue

            spread_pct = get_bid_ask_spread_pct(opt)
            liquidity = calculate_liquidity_score(
                opt.volume, opt.open_interest, spread_pct,
                self.min_volume, self.min_open_interest
            )

            # Calculate theoretical value using realized vol
            bs_realized = BlackScholes(spot, opt.strike, self.rate, realized_vol, time_to_exp)

            if opt.option_type == 'call':
                theo_price = bs_realized.call_price()
            else:
                theo_price = bs_realized.put_price()

            edge_mid = theo_price - mid
            edge_pct_mid = (edge_mid / mid) * 100 if mid > 0 else 0

            # Significant discount (IV < realized by 20%+) - BUY opportunity
            if iv_ratio < 0.80 and edge_pct_mid >= self.min_edge_pct:
                # To buy, we pay the ASK
                buy_price = opt.ask if opt.ask else mid
                executable_edge = theo_price - buy_price
                executable_edge_pct = (executable_edge / buy_price) * 100 if buy_price > 0 else 0

                # Only flag if edge survives the spread
                if executable_edge_pct >= 2.0:
                    opportunities.append(MispricingOpportunity(
                        symbol=symbol,
                        opportunity_type="iv_discount",
                        description=f"{opt.option_type.upper()} ${opt.strike} IV ({iv*100:.0f}%) << RV ({realized_vol*100:.0f}%)",
                        theoretical_value=theo_price,
                        market_value=mid,
                        edge=edge_mid,
                        edge_pct=edge_pct_mid,
                        confidence=0.7 if executable_edge_pct > 5 else 0.5,
                        suggested_trade=f"Buy {symbol} ${opt.strike} {opt.option_type.upper()} @${buy_price:.2f} ({expiry})",
                        risk_reward=executable_edge_pct / 20,
                        executable_edge=executable_edge,
                        executable_edge_pct=executable_edge_pct,
                        bid_ask_spread_pct=spread_pct,
                        volume=opt.volume,
                        open_interest=opt.open_interest,
                        liquidity_score=liquidity,
                    ))

            # Significant premium (IV > realized by 50%+) - SELL opportunity
            elif iv_ratio > 1.50 and abs(edge_pct_mid) >= self.min_edge_pct:
                # To sell, we receive the BID
                sell_price = opt.bid if opt.bid else mid
                executable_edge = sell_price - theo_price
                executable_edge_pct = (executable_edge / sell_price) * 100 if sell_price > 0 else 0

                # Only flag if edge survives the spread
                if executable_edge_pct >= 2.0:
                    opportunities.append(MispricingOpportunity(
                        symbol=symbol,
                        opportunity_type="iv_premium",
                        description=f"{opt.option_type.upper()} ${opt.strike} IV ({iv*100:.0f}%) >> RV ({realized_vol*100:.0f}%)",
                        theoretical_value=theo_price,
                        market_value=mid,
                        edge=-edge_mid,
                        edge_pct=-edge_pct_mid,
                        confidence=0.6 if executable_edge_pct > 5 else 0.4,
                        suggested_trade=f"Sell {symbol} ${opt.strike} {opt.option_type.upper()} @${sell_price:.2f} ({expiry})",
                        risk_reward=executable_edge_pct / 30,
                        executable_edge=executable_edge,
                        executable_edge_pct=executable_edge_pct,
                        bid_ask_spread_pct=spread_pct,
                        volume=opt.volume,
                        open_interest=opt.open_interest,
                        liquidity_score=liquidity,
                    ))

        return opportunities

    def _check_skew_anomalies(
        self,
        symbol: str,
        spot: float,
        options: list[OptionContract],
        time_to_exp: float,
        expiry: str,
    ) -> list[MispricingOpportunity]:
        """
        Check for unusual IV skew patterns.

        Normal skew: OTM puts have higher IV than OTM calls
        Anomaly: Deviation from typical skew pattern

        Only flags opportunities where executable edge survives bid-ask spread.
        """
        opportunities = []

        # Get liquid puts and calls
        puts = [o for o in options if o.option_type == 'put'
                and self._passes_liquidity_filter(o) and o.implied_volatility]
        calls = [o for o in options if o.option_type == 'call'
                 and self._passes_liquidity_filter(o) and o.implied_volatility]

        if len(puts) < 3 or len(calls) < 3:
            return opportunities

        # Calculate ATM IV (closest to spot)
        all_opts = puts + calls
        atm_opt = min(all_opts, key=lambda o: abs(o.strike - spot))
        atm_iv = atm_opt.implied_volatility

        # Check for unusually cheap/expensive strikes
        for opt in all_opts:
            moneyness = opt.strike / spot
            iv = opt.implied_volatility

            # Expected IV based on simple skew model
            if opt.option_type == 'put' and moneyness < 0.95:
                # OTM put - expect IV premium
                expected_iv = atm_iv * (1 + 0.1 * (1 - moneyness) / 0.1)
            elif opt.option_type == 'call' and moneyness > 1.05:
                # OTM call - expect slight IV discount
                expected_iv = atm_iv * (1 - 0.05 * (moneyness - 1) / 0.1)
            else:
                continue

            iv_deviation = (iv - expected_iv) / expected_iv

            # Flag significant deviations (>20%)
            if abs(iv_deviation) > 0.20:
                mid = (opt.bid + opt.ask) / 2 if opt.bid and opt.ask else opt.last
                if not mid or mid <= 0:
                    continue

                spread_pct = get_bid_ask_spread_pct(opt)
                liquidity = calculate_liquidity_score(
                    opt.volume, opt.open_interest, spread_pct,
                    self.min_volume, self.min_open_interest
                )

                bs_expected = BlackScholes(spot, opt.strike, self.rate, expected_iv, time_to_exp)

                if opt.option_type == 'call':
                    theo = bs_expected.call_price()
                else:
                    theo = bs_expected.put_price()

                edge_mid = theo - mid
                edge_pct_mid = (edge_mid / mid) * 100 if mid > 0 else 0

                if abs(edge_pct_mid) >= self.min_edge_pct:
                    if iv_deviation < 0:
                        # IV too low - BUY at ask
                        buy_price = opt.ask if opt.ask else mid
                        executable_edge = theo - buy_price
                        executable_edge_pct = (executable_edge / buy_price) * 100 if buy_price > 0 else 0
                        trade = f"Buy {symbol} ${opt.strike} {opt.option_type.upper()} @${buy_price:.2f}"
                        desc = "IV unusually low for this strike"
                    else:
                        # IV too high - SELL at bid
                        sell_price = opt.bid if opt.bid else mid
                        executable_edge = sell_price - theo
                        executable_edge_pct = (executable_edge / sell_price) * 100 if sell_price > 0 else 0
                        trade = f"Sell {symbol} ${opt.strike} {opt.option_type.upper()} @${sell_price:.2f}"
                        desc = "IV unusually high for this strike"

                    # Only include if executable edge is meaningful
                    if executable_edge_pct >= 2.0:
                        opportunities.append(MispricingOpportunity(
                            symbol=symbol,
                            opportunity_type="skew_anomaly",
                            description=f"{desc} ({expiry})",
                            theoretical_value=theo,
                            market_value=mid,
                            edge=edge_mid,
                            edge_pct=edge_pct_mid,
                            confidence=0.5 if executable_edge_pct > 5 else 0.3,
                            suggested_trade=trade,
                            risk_reward=abs(executable_edge_pct) / 25,
                            executable_edge=executable_edge,
                            executable_edge_pct=executable_edge_pct,
                            bid_ask_spread_pct=spread_pct,
                            volume=opt.volume,
                            open_interest=opt.open_interest,
                            liquidity_score=liquidity,
                        ))

        return opportunities

    def scan_watchlist(
        self,
        symbols: list[str],
        sort_by: str = "executable_edge_pct",
        actionable_only: bool = True,
    ) -> pd.DataFrame:
        """
        Scan multiple symbols and return sorted opportunities.

        Args:
            symbols: List of symbols to scan
            sort_by: Column to sort by (default: executable_edge_pct)
            actionable_only: If True, only return actionable opportunities

        Returns:
            DataFrame of opportunities
        """
        all_opportunities = []

        for symbol in symbols:
            logger.info(f"Scanning {symbol}...")
            opps = self.scan_symbol(symbol)
            if actionable_only:
                opps = [o for o in opps if o.is_actionable]
            all_opportunities.extend(opps)

        if not all_opportunities:
            return pd.DataFrame()

        df = pd.DataFrame([
            {
                'symbol': o.symbol,
                'type': o.opportunity_type,
                'description': o.description,
                'theo_edge%': round(o.edge_pct, 1),
                'exec_edge%': round(o.executable_edge_pct, 1),
                'spread%': round(o.bid_ask_spread_pct, 1),
                'liquidity': round(o.liquidity_score, 2),
                'confidence': o.confidence,
                'trade': o.suggested_trade,
                'volume': o.volume,
                'OI': o.open_interest,
                'actionable': o.is_actionable,
            }
            for o in all_opportunities
        ])

        # Sort by executable edge percentage (absolute value)
        if 'exec_edge%' in df.columns:
            df['abs_exec_edge'] = df['exec_edge%'].abs()
            df = df.sort_values('abs_exec_edge', ascending=False)
            df = df.drop('abs_exec_edge', axis=1)

        return df

    def get_best_opportunities(
        self,
        symbols: list[str],
        top_n: int = 10,
        min_confidence: float = 0.5,
        require_actionable: bool = True,
    ) -> list[MispricingOpportunity]:
        """
        Get the best opportunities from a watchlist.

        Args:
            symbols: Symbols to scan
            top_n: Number of top opportunities to return
            min_confidence: Minimum confidence threshold
            require_actionable: If True, only return actionable opportunities

        Returns:
            List of top opportunities sorted by executable edge
        """
        all_opps = []

        for symbol in symbols:
            opps = self.scan_symbol(symbol)
            for o in opps:
                if o.confidence >= min_confidence:
                    if require_actionable and not o.is_actionable:
                        continue
                    all_opps.append(o)

        # Sort by executable edge percentage
        all_opps.sort(key=lambda o: abs(o.executable_edge_pct), reverse=True)

        return all_opps[:top_n]
