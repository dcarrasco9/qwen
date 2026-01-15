"""
Options Mispricing Detection

Identifies potential arbitrage and value opportunities in options markets:
1. Put-Call Parity Violations
2. Implied vs Realized Volatility Discrepancies
3. Skew Anomalies
4. Term Structure Opportunities
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Literal
import numpy as np
import pandas as pd

from qwen.pricing import BlackScholes
from qwen.data.base import DataProvider, OptionContract


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

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    @property
    def is_actionable(self) -> bool:
        """Check if opportunity meets minimum thresholds."""
        return abs(self.edge_pct) > 5 and self.confidence > 0.6


class MispricingScanner:
    """
    Scans options chains for mispricing opportunities.

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
    ):
        """
        Initialize scanner.

        Args:
            data_provider: Data provider for quotes and chains
            risk_free_rate: Risk-free rate for calculations
            min_edge_pct: Minimum edge percentage to flag
            min_volume: Minimum option volume to consider
        """
        self.provider = data_provider
        self.rate = risk_free_rate
        self.min_edge_pct = min_edge_pct
        self.min_volume = min_volume

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
            print(f"Error scanning {symbol}: {e}")

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
        Check for put-call parity violations.

        Put-Call Parity: C - P = S - K*e^(-rT)

        If violated, there's a risk-free arbitrage opportunity.
        """
        opportunities = []

        # Group by strike
        calls = {o.strike: o for o in options if o.option_type == 'call'}
        puts = {o.strike: o for o in options if o.option_type == 'put'}

        for strike in set(calls.keys()) & set(puts.keys()):
            call = calls[strike]
            put = puts[strike]

            # Skip low volume
            if call.volume < self.min_volume or put.volume < self.min_volume:
                continue

            # Use mid prices
            call_mid = (call.bid + call.ask) / 2 if call.bid and call.ask else call.last_price
            put_mid = (put.bid + put.ask) / 2 if put.bid and put.ask else put.last_price

            if not call_mid or not put_mid:
                continue

            # Theoretical relationship
            pv_strike = strike * np.exp(-self.rate * time_to_exp)
            theoretical_diff = spot - pv_strike  # C - P should equal this
            actual_diff = call_mid - put_mid

            parity_violation = actual_diff - theoretical_diff

            # If violation is significant (> transaction costs)
            if abs(parity_violation) > 0.10:  # $0.10 threshold
                edge_pct = (parity_violation / call_mid) * 100

                if abs(edge_pct) >= self.min_edge_pct:
                    if parity_violation > 0:
                        # Call overpriced relative to put
                        trade = f"Sell {symbol} ${strike} Call, Buy ${strike} Put, Buy Stock"
                    else:
                        # Put overpriced relative to call
                        trade = f"Sell {symbol} ${strike} Put, Buy ${strike} Call, Short Stock"

                    opportunities.append(MispricingOpportunity(
                        symbol=symbol,
                        opportunity_type="put_call_parity",
                        description=f"Put-call parity violation at ${strike} strike ({expiry})",
                        theoretical_value=theoretical_diff,
                        market_value=actual_diff,
                        edge=parity_violation,
                        edge_pct=edge_pct,
                        confidence=0.9,  # High confidence - mathematical relationship
                        suggested_trade=trade,
                        risk_reward=10.0,  # Theoretically risk-free
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

        - IV << Realized: Options are cheap (buy)
        - IV >> Realized: Options are expensive (sell)
        """
        opportunities = []

        for opt in options:
            if opt.volume < self.min_volume:
                continue

            iv = opt.implied_volatility
            if not iv or iv <= 0:
                continue

            # Calculate IV premium/discount vs realized
            iv_diff = iv - realized_vol
            iv_ratio = iv / realized_vol if realized_vol > 0 else 1

            # Get mid price
            mid = (opt.bid + opt.ask) / 2 if opt.bid and opt.ask else opt.last_price
            if not mid:
                continue

            # Calculate theoretical value using realized vol
            bs_realized = BlackScholes(spot, opt.strike, self.rate, realized_vol, time_to_exp)
            bs_market = BlackScholes(spot, opt.strike, self.rate, iv, time_to_exp)

            if opt.option_type == 'call':
                theo_price = bs_realized.call_price()
                market_price = bs_market.call_price()
            else:
                theo_price = bs_realized.put_price()
                market_price = bs_market.put_price()

            edge = theo_price - mid
            edge_pct = (edge / mid) * 100 if mid > 0 else 0

            # Significant discount (IV < realized by 20%+)
            if iv_ratio < 0.80 and abs(edge_pct) >= self.min_edge_pct:
                opportunities.append(MispricingOpportunity(
                    symbol=symbol,
                    opportunity_type="iv_discount",
                    description=f"{opt.option_type.upper()} ${opt.strike} IV ({iv*100:.0f}%) << Realized ({realized_vol*100:.0f}%)",
                    theoretical_value=theo_price,
                    market_value=mid,
                    edge=edge,
                    edge_pct=edge_pct,
                    confidence=0.7,
                    suggested_trade=f"Buy {symbol} ${opt.strike} {opt.option_type.upper()} ({expiry})",
                    risk_reward=edge_pct / 20,  # Rough R:R estimate
                ))

            # Significant premium (IV > realized by 50%+)
            elif iv_ratio > 1.50 and abs(edge_pct) >= self.min_edge_pct:
                opportunities.append(MispricingOpportunity(
                    symbol=symbol,
                    opportunity_type="iv_premium",
                    description=f"{opt.option_type.upper()} ${opt.strike} IV ({iv*100:.0f}%) >> Realized ({realized_vol*100:.0f}%)",
                    theoretical_value=theo_price,
                    market_value=mid,
                    edge=-edge,  # Negative because we want to sell
                    edge_pct=-edge_pct,
                    confidence=0.6,
                    suggested_trade=f"Sell {symbol} ${opt.strike} {opt.option_type.upper()} ({expiry})",
                    risk_reward=abs(edge_pct) / 30,
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
        """
        opportunities = []

        # Get puts and calls with volume
        puts = [o for o in options if o.option_type == 'put'
                and o.volume >= self.min_volume and o.implied_volatility]
        calls = [o for o in options if o.option_type == 'call'
                 and o.volume >= self.min_volume and o.implied_volatility]

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
            # OTM puts (moneyness < 1): IV should be higher
            # OTM calls (moneyness > 1): IV should be lower
            if opt.option_type == 'put' and moneyness < 0.95:
                # OTM put - expect IV premium
                expected_iv = atm_iv * (1 + 0.1 * (1 - moneyness) / 0.1)
            elif opt.option_type == 'call' and moneyness > 1.05:
                # OTM call - expect slight IV discount
                expected_iv = atm_iv * (1 - 0.05 * (moneyness - 1) / 0.1)
            else:
                continue

            iv_deviation = (iv - expected_iv) / expected_iv

            # Flag significant deviations
            if abs(iv_deviation) > 0.20:  # 20% deviation from expected
                mid = (opt.bid + opt.ask) / 2 if opt.bid and opt.ask else opt.last_price
                if not mid:
                    continue

                bs_expected = BlackScholes(spot, opt.strike, self.rate, expected_iv, time_to_exp)
                bs_actual = BlackScholes(spot, opt.strike, self.rate, iv, time_to_exp)

                if opt.option_type == 'call':
                    theo = bs_expected.call_price()
                    actual = bs_actual.call_price()
                else:
                    theo = bs_expected.put_price()
                    actual = bs_actual.put_price()

                edge = theo - mid
                edge_pct = (edge / mid) * 100 if mid > 0 else 0

                if abs(edge_pct) >= self.min_edge_pct:
                    if iv_deviation < 0:
                        trade = f"Buy {symbol} ${opt.strike} {opt.option_type.upper()}"
                        desc = "IV unusually low for this strike"
                    else:
                        trade = f"Sell {symbol} ${opt.strike} {opt.option_type.upper()}"
                        desc = "IV unusually high for this strike"

                    opportunities.append(MispricingOpportunity(
                        symbol=symbol,
                        opportunity_type="skew_anomaly",
                        description=f"{desc} ({expiry})",
                        theoretical_value=theo,
                        market_value=mid,
                        edge=edge,
                        edge_pct=edge_pct,
                        confidence=0.5,
                        suggested_trade=trade,
                        risk_reward=abs(edge_pct) / 25,
                    ))

        return opportunities

    def scan_watchlist(
        self,
        symbols: list[str],
        sort_by: str = "edge_pct",
    ) -> pd.DataFrame:
        """
        Scan multiple symbols and return sorted opportunities.

        Args:
            symbols: List of symbols to scan
            sort_by: Column to sort by

        Returns:
            DataFrame of opportunities
        """
        all_opportunities = []

        for symbol in symbols:
            print(f"Scanning {symbol}...")
            opps = self.scan_symbol(symbol)
            all_opportunities.extend(opps)

        if not all_opportunities:
            return pd.DataFrame()

        df = pd.DataFrame([
            {
                'symbol': o.symbol,
                'type': o.opportunity_type,
                'description': o.description,
                'edge': o.edge,
                'edge_pct': o.edge_pct,
                'confidence': o.confidence,
                'trade': o.suggested_trade,
                'risk_reward': o.risk_reward,
                'actionable': o.is_actionable,
            }
            for o in all_opportunities
        ])

        # Sort by absolute edge percentage
        df['abs_edge_pct'] = df['edge_pct'].abs()
        df = df.sort_values('abs_edge_pct', ascending=False)
        df = df.drop('abs_edge_pct', axis=1)

        return df

    def get_best_opportunities(
        self,
        symbols: list[str],
        top_n: int = 10,
        min_confidence: float = 0.5,
    ) -> list[MispricingOpportunity]:
        """
        Get the best opportunities from a watchlist.

        Args:
            symbols: Symbols to scan
            top_n: Number of top opportunities to return
            min_confidence: Minimum confidence threshold

        Returns:
            List of top opportunities
        """
        all_opps = []

        for symbol in symbols:
            opps = self.scan_symbol(symbol)
            all_opps.extend([o for o in opps if o.confidence >= min_confidence])

        # Sort by edge percentage
        all_opps.sort(key=lambda o: abs(o.edge_pct), reverse=True)

        return all_opps[:top_n]
